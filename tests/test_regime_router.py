"""Tests for the regime router + the three fusion strategies."""
from __future__ import annotations

import numpy as np
import pytest

from models.early_fusion import EARLY_CONVERSION_CAP, early_fusion
from models.late_fusion import late_fusion
from models.mid_fusion import MID_CONVERSION_CAP, mid_fusion
from models.regime_router import (
    EARLY_LAST_ROUND,
    MID_LAST_ROUND,
    Regime,
    classify_regime,
    regime_fuse_one_stream,
    regime_fuse_podium_and_win,
)


# --------------------------------------------------------------------------- #
# classify_regime
# --------------------------------------------------------------------------- #


def test_round_1_is_early() -> None:
    assert classify_regime(1) is Regime.EARLY


def test_round_8_is_early_boundary() -> None:
    assert classify_regime(EARLY_LAST_ROUND) is Regime.EARLY


def test_round_9_is_mid() -> None:
    assert classify_regime(EARLY_LAST_ROUND + 1) is Regime.MID


def test_round_16_is_mid_boundary() -> None:
    assert classify_regime(MID_LAST_ROUND) is Regime.MID


def test_round_17_is_late() -> None:
    assert classify_regime(MID_LAST_ROUND + 1) is Regime.LATE


def test_round_24_is_late() -> None:
    assert classify_regime(24) is Regime.LATE


def test_round_zero_or_negative_defaults_to_early() -> None:
    assert classify_regime(0) is Regime.EARLY
    assert classify_regime(-3) is Regime.EARLY


# --------------------------------------------------------------------------- #
# early_fusion
# --------------------------------------------------------------------------- #


def test_early_fusion_v0_uses_capped_conversion_weight() -> None:
    pe = np.array([0.40, 0.20, 0.10])
    pc = np.array([0.80, 0.05, 0.25])
    out = early_fusion(pe, pc, volatility=0.0)
    expected = (1 - EARLY_CONVERSION_CAP) * pe + EARLY_CONVERSION_CAP * pc
    np.testing.assert_allclose(out, expected, atol=1e-12)


def test_early_fusion_v1_drops_conversion_entirely() -> None:
    pe = np.array([0.40, 0.20, 0.10])
    pc = np.array([0.80, 0.05, 0.25])
    out = early_fusion(pe, pc, volatility=1.0)
    np.testing.assert_allclose(out, pe, atol=1e-12)


def test_early_fusion_clipped_to_unit_interval() -> None:
    pe = np.array([0.95, 0.10])
    pc = np.array([1.20, -0.30])  # adversarial out-of-range
    out = early_fusion(pe, pc, volatility=0.0)
    assert (out >= 0.0).all()
    assert (out <= 1.0).all()


# --------------------------------------------------------------------------- #
# mid_fusion
# --------------------------------------------------------------------------- #


def test_mid_fusion_v0_gives_balanced_blend() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = mid_fusion(pe, pc, volatility=0.0)
    expected = (1 - MID_CONVERSION_CAP) * pe + MID_CONVERSION_CAP * pc
    np.testing.assert_allclose(out, expected, atol=1e-12)


def test_mid_fusion_v1_drops_conversion_entirely() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = mid_fusion(pe, pc, volatility=1.0)
    np.testing.assert_allclose(out, pe, atol=1e-12)


def test_mid_fusion_preserves_distribution_shape() -> None:
    """No shrinkage toward mean — relative ordering of pe is preserved
    so long as pc also preserves it. The output should not be a flatter
    distribution than the inputs."""
    pe = np.array([0.50, 0.30, 0.15, 0.05])
    pc = np.array([0.70, 0.20, 0.07, 0.03])
    out = mid_fusion(pe, pc, volatility=0.5)
    # Strict ordering preserved.
    assert out[0] > out[1] > out[2] > out[3]


def test_mid_fusion_at_v_half() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = mid_fusion(pe, pc, volatility=0.5)
    # cap=0.5 → w_conv = 0.5 * (1-0.5) = 0.25 → 75% pe + 25% pc
    expected = 0.75 * pe + 0.25 * pc
    np.testing.assert_allclose(out, expected, atol=1e-12)


# --------------------------------------------------------------------------- #
# late_fusion
# --------------------------------------------------------------------------- #


def test_late_fusion_v0_uses_pure_conversion() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = late_fusion(pe, pc, volatility=0.0)
    np.testing.assert_allclose(out, pc, atol=1e-12)


def test_late_fusion_v1_uses_pure_elite() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = late_fusion(pe, pc, volatility=1.0)
    np.testing.assert_allclose(out, pe, atol=1e-12)


def test_late_fusion_v_half_is_average() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    out = late_fusion(pe, pc, volatility=0.5)
    expected = 0.5 * pe + 0.5 * pc
    np.testing.assert_allclose(out, expected, atol=1e-12)


# --------------------------------------------------------------------------- #
# dispatcher
# --------------------------------------------------------------------------- #


def test_regime_fuse_dispatches_correctly_by_round() -> None:
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    v = 0.5
    # Round 4 → EARLY
    early_out = regime_fuse_one_stream(pe, pc, volatility=v, target_round=4)
    expected_early = early_fusion(pe, pc, volatility=v)
    np.testing.assert_allclose(early_out, expected_early, atol=1e-12)
    # Round 12 → MID
    mid_out = regime_fuse_one_stream(pe, pc, volatility=v, target_round=12)
    expected_mid = mid_fusion(pe, pc, volatility=v)
    np.testing.assert_allclose(mid_out, expected_mid, atol=1e-12)
    # Round 20 → LATE
    late_out = regime_fuse_one_stream(pe, pc, volatility=v, target_round=20)
    expected_late = late_fusion(pe, pc, volatility=v)
    np.testing.assert_allclose(late_out, expected_late, atol=1e-12)


def test_dual_stream_returns_regime() -> None:
    pe_pod = np.array([0.50, 0.30, 0.10])
    pe_win = np.array([0.30, 0.20, 0.05])
    pc_pod = np.array([0.70, 0.15, 0.10])
    pc_win = np.array([0.50, 0.10, 0.05])
    p_pod, p_win, regime = regime_fuse_podium_and_win(
        pe_pod, pe_win, pc_pod, pc_win, volatility=0.5, target_round=12
    )
    assert regime is Regime.MID
    assert p_pod.shape == pe_pod.shape
    assert p_win.shape == pe_win.shape
    assert (p_pod >= 0.0).all() and (p_pod <= 1.0).all()
    assert (p_win >= 0.0).all() and (p_win <= 1.0).all()


def test_all_three_regimes_converge_to_pe_at_v1() -> None:
    """High V → all regimes drop conversion → result is pe."""
    pe = np.array([0.40, 0.20, 0.10])
    pc = np.array([0.80, 0.05, 0.25])
    for target_round in (3, 12, 20):
        out = regime_fuse_one_stream(pe, pc, volatility=1.0, target_round=target_round)
        np.testing.assert_allclose(out, pe, atol=1e-12)
