"""Tests for models.probabilistic_combine."""
from __future__ import annotations

import numpy as np
import pytest

from models.probabilistic_combine import (
    calibration_error_10_bin,
    fuse_probabilities,
    podium_log_loss,
    renormalize_probabilities,
    rerank_with_probabilistic,
    winner_log_loss,
)


def test_fusion_math_correctness_v_for_conversion():
    pe_pod = np.array([0.9, 0.6, 0.3, 0.1])
    pe_win = np.array([0.5, 0.2, 0.05, 0.0])
    pc_pod = np.array([0.5, 0.7, 0.4, 0.2])
    pc_win = np.array([0.1, 0.5, 0.2, 0.05])
    V = 0.25
    final_pod, final_win = fuse_probabilities(
        pe_pod, pe_win, pc_pod, pc_win, V, fusion="v_for_conversion"
    )
    expected_pod = (1 - V) * pe_pod + V * pc_pod
    expected_win = (1 - V) * pe_win + V * pc_win
    np.testing.assert_allclose(final_pod, np.clip(expected_pod, 0.0, 1.0))
    np.testing.assert_allclose(final_win, np.clip(expected_win, 0.0, 1.0))


def test_fusion_math_v_for_elite_is_mirrored():
    pe_pod = np.array([0.9, 0.6, 0.3, 0.1])
    pe_win = np.array([0.5, 0.2, 0.05, 0.0])
    pc_pod = np.array([0.5, 0.7, 0.4, 0.2])
    pc_win = np.array([0.1, 0.5, 0.2, 0.05])
    V = 0.7
    final_pod_a, _ = fuse_probabilities(
        pe_pod, pe_win, pc_pod, pc_win, V, fusion="v_for_conversion"
    )
    final_pod_b, _ = fuse_probabilities(
        pe_pod, pe_win, pc_pod, pc_win, V, fusion="v_for_elite"
    )
    # Swapping the role of V should yield (1-V')*pe + V'*pc with V' = 1-V.
    expected_b = (1 - V) * pc_pod + V * pe_pod
    np.testing.assert_allclose(final_pod_b, np.clip(expected_b, 0.0, 1.0))
    assert not np.allclose(final_pod_a, final_pod_b)


def test_monotonicity_in_v_when_conversion_higher():
    """If P_conv > P_elite for a driver, increasing V should increase P_final
    under v_for_conversion."""
    pe = np.array([0.3])
    pc = np.array([0.7])
    v_low = 0.1
    v_high = 0.9
    pod_low, _ = fuse_probabilities(pe, pe, pc, pc, v_low, "v_for_conversion")
    pod_high, _ = fuse_probabilities(pe, pe, pc, pc, v_high, "v_for_conversion")
    assert pod_high[0] > pod_low[0]


def test_renormalize_p_win_sums_to_one():
    p_pod = np.array([0.5, 0.5, 0.5, 0.5])
    p_win = np.array([0.25, 0.25, 0.1, 0.1])
    p_pod_out, p_win_out = renormalize_probabilities(p_pod, p_win)
    assert abs(float(p_win_out.sum()) - 1.0) < 1e-9
    assert abs(float(p_pod_out.sum()) - 3.0) < 1e-9


def test_renormalize_handles_all_zeros():
    p_pod = np.zeros(5)
    p_win = np.zeros(5)
    p_pod_out, p_win_out = renormalize_probabilities(p_pod, p_win)
    # Uniform fallback.
    np.testing.assert_allclose(p_win_out, np.full(5, 0.2))
    np.testing.assert_allclose(p_pod_out, np.full(5, 0.6))


def test_rerank_keeps_outside_top_n_unchanged():
    anchor = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    # P_final has driver-index-2 with the highest podium score → should bubble
    # to position 1 of the re-rank.
    p_final = np.array([0.3, 0.4, 0.9, 0.2, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05])
    new_ranks = rerank_with_probabilistic(anchor, p_final, top_n=6)
    assert new_ranks[2] == 1  # index 2 should now be position 1
    # Positions 7..10 (zero-based index 6..9) unchanged.
    np.testing.assert_array_equal(new_ranks[6:10], [7, 8, 9, 10])


def test_rerank_top_n_window_doesnt_pull_in_position_7():
    """A high-P_final driver currently at position 8 should NOT bubble up
    because the top-N window is 6."""
    anchor = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    p_final = np.array([0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.05, 0.99, 0.05, 0.05])
    new_ranks = rerank_with_probabilistic(anchor, p_final, top_n=6)
    # The driver at position 8 stays at position 8.
    assert new_ranks[7] == 8


def test_winner_log_loss_epsilon_clipping():
    """A predicted P(win) of 0 for the actual winner should not return inf."""
    p_win = np.array([0.0, 0.5, 0.5, 0.0])
    loss = winner_log_loss(p_win, actual_winner_idx=0)
    assert np.isfinite(loss)
    assert loss > 10.0  # very large but bounded


def test_podium_log_loss_well_defined():
    p_pod = np.array([0.9, 0.8, 0.7, 0.05, 0.05])
    mask = np.array([True, True, True, False, False])
    loss = podium_log_loss(p_pod, mask)
    assert np.isfinite(loss)
    assert loss >= 0.0


def test_calibration_error_zero_when_perfect():
    p = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
    y = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
    err = calibration_error_10_bin(p, y, n_bins=10)
    assert err < 1e-6


def test_calibration_error_nonzero_when_miscalibrated():
    p = np.array([0.9, 0.9, 0.9, 0.1, 0.1])
    y = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
    err = calibration_error_10_bin(p, y, n_bins=10)
    assert err > 0.5


def test_invalid_fusion_raises():
    with pytest.raises(ValueError):
        fuse_probabilities(
            np.array([0.5]), np.array([0.5]), np.array([0.5]), np.array([0.5]),
            volatility=0.5,
            fusion="not-a-mode",  # type: ignore[arg-type]
        )
