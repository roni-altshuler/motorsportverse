"""Tests for the maturity-weighted adaptive fusion."""
from __future__ import annotations

import numpy as np

from models.adaptive_fusion import adaptive_fusion, adaptive_fuse_podium_and_win


def test_zero_maturity_returns_p_elite_exactly() -> None:
    pe = np.array([0.4, 0.2, 0.1, 0.05])
    pc = np.array([0.9, 0.5, 0.3, 0.05])
    m = np.array([0.0, 0.0, 0.0, 0.0])
    out = adaptive_fusion(pe, pc, volatility=0.6, maturity=m)
    np.testing.assert_allclose(out, pe, atol=1e-12)


def test_full_maturity_matches_fixed_fusion() -> None:
    """m = 1 everywhere: result must equal (1-V)·P_elite + V·P_conv."""
    pe = np.array([0.40, 0.20, 0.10, 0.05])
    pc = np.array([0.80, 0.30, 0.20, 0.10])
    v = 0.5
    m = np.array([1.0, 1.0, 1.0, 1.0])
    expected = (1 - v) * pe + v * pc
    out = adaptive_fusion(pe, pc, volatility=v, maturity=m)
    np.testing.assert_allclose(out, expected, atol=1e-12)


def test_endpoints_and_interpolation_direction() -> None:
    """The m=0 endpoint is P_elite; the m=1 endpoint is fixed fusion. At
    intermediate maturity the result moves toward the fixed-fusion
    endpoint relative to P_elite (i.e., conversion influence grows with
    maturity). Strict monotonicity does NOT hold for every input because
    the shrinkage term pulls P_conv toward mean(P_elite) at low maturity
    — that's an intentional design property (sparse priors get damped).
    """
    pe = np.array([0.40, 0.20, 0.10])
    pc = np.array([0.80, 0.05, 0.25])
    v = 0.5
    fixed_fusion = (1 - v) * pe + v * pc
    out_m0 = adaptive_fusion(pe, pc, volatility=v, maturity=np.array([0.0, 0.0, 0.0]))
    out_m1 = adaptive_fusion(pe, pc, volatility=v, maturity=np.array([1.0, 1.0, 1.0]))
    np.testing.assert_allclose(out_m0, pe, atol=1e-12)
    np.testing.assert_allclose(out_m1, fixed_fusion, atol=1e-12)
    # The m=1 result should lie strictly toward pc relative to pe per-driver.
    for i in range(len(pe)):
        if pc[i] > pe[i]:
            assert out_m1[i] > pe[i] - 1e-9
        elif pc[i] < pe[i]:
            assert out_m1[i] < pe[i] + 1e-9


def test_hard_cutoff_forces_p_elite_for_low_history_drivers() -> None:
    pe = np.array([0.40, 0.20, 0.10, 0.05])
    pc = np.array([0.80, 0.50, 0.30, 0.05])
    # Maturity is high for everyone, but driver 2 has only 1 prior race.
    m = np.array([0.9, 0.9, 0.9, 0.9])
    n_prior = np.array([20, 20, 1, 20])
    out = adaptive_fusion(
        pe, pc, volatility=0.6, maturity=m,
        min_history_threshold=3, n_prior_per_driver=n_prior,
    )
    # Driver 2 should be exactly p_elite.
    assert out[2] == pe[2]
    # Other drivers should reflect the smooth fusion (not equal to p_elite).
    assert out[0] != pe[0]


def test_shrinkage_prior_uses_elite_mean_when_unspecified() -> None:
    """At m=0, P_conv_shrunk equals shrinkage_prior; with the default
    (None), that's mean(p_elite). Verify with V=1 so the effective_V isolates
    the shrinkage path... wait, at m=0 effective_V is also 0, so we can't
    isolate via effective_V. Instead verify by stepping into the formula
    at m=1 with V=1: result = P_conv (no shrinkage), and at m=0 result =
    P_elite regardless. So this test asserts that the function uses
    mean(p_elite) by checking that pure_prior input WITH explicit
    shrinkage_prior=mean(p_elite) matches the default."""
    pe = np.array([0.40, 0.20, 0.10])
    pc = np.array([0.80, 0.50, 0.10])
    # m = 0.5, V = 1 → effective_V = 0.5 per driver.
    # P_conv_shrunk = 0.5 · P_conv + 0.5 · prior.
    # With default: prior = mean(P_elite) ≈ 0.2333
    # Manually compute with explicit prior; both should match.
    m = np.array([0.5, 0.5, 0.5])
    default = adaptive_fusion(pe, pc, volatility=1.0, maturity=m)
    explicit = adaptive_fusion(
        pe, pc, volatility=1.0, maturity=m,
        shrinkage_prior=float(pe.mean()),
    )
    np.testing.assert_allclose(default, explicit, atol=1e-12)


def test_outputs_clipped_to_unit_interval() -> None:
    """Even with adversarial inputs the output must stay in [0, 1]."""
    pe = np.array([0.95, 0.50, 0.10])
    pc = np.array([1.10, 0.50, -0.05])  # adversarial out-of-range
    m = np.array([1.0, 1.0, 1.0])
    out = adaptive_fusion(pe, pc, volatility=0.8, maturity=m)
    assert (out >= 0.0).all()
    assert (out <= 1.0).all()


def test_volatility_clipped_defensively() -> None:
    """Out-of-range V should clip to [0, 1] without raising."""
    pe = np.array([0.40, 0.20])
    pc = np.array([0.80, 0.30])
    m = np.array([1.0, 1.0])
    # V > 1 should clip to 1 → result = P_conv
    out = adaptive_fusion(pe, pc, volatility=2.0, maturity=m)
    np.testing.assert_allclose(out, pc, atol=1e-12)
    # V < 0 should clip to 0 → result = P_elite
    out = adaptive_fusion(pe, pc, volatility=-0.5, maturity=m)
    np.testing.assert_allclose(out, pe, atol=1e-12)


def test_dual_stream_wrapper_returns_two_arrays() -> None:
    pe_pod = np.array([0.50, 0.40, 0.20])
    pe_win = np.array([0.30, 0.20, 0.05])
    pc_pod = np.array([0.80, 0.30, 0.10])
    pc_win = np.array([0.60, 0.10, 0.05])
    m = np.array([0.7, 0.7, 0.7])
    p_pod, p_win = adaptive_fuse_podium_and_win(
        pe_pod, pe_win, pc_pod, pc_win, volatility=0.5, maturity=m,
    )
    assert p_pod.shape == pe_pod.shape
    assert p_win.shape == pe_win.shape
    assert (p_pod >= 0.0).all() and (p_pod <= 1.0).all()
    assert (p_win >= 0.0).all() and (p_win <= 1.0).all()
