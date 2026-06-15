"""Focused unit tests for the extracted core modules (calibration, drift,
promotion). These exercise the public APIs directly — no F1 CLI coupling."""

import math

import pytest

from motorsport_core import calibration, drift, promotion


# --------------------------------------------------------------------------- #
# calibration — Plackett-Luce sampler
# --------------------------------------------------------------------------- #


def test_plackett_luce_probabilities_well_formed():
    lap_times = {"A": 90.0, "B": 90.3, "C": 90.6, "D": 91.0, "E": 91.5}
    probs = calibration.plackett_luce_probabilities(lap_times, n_samples=2000, seed=42)
    assert set(probs.drivers) == set(lap_times)
    # win probabilities sum to ~1 across the field
    assert math.isclose(sum(probs.p_win.values()), 1.0, abs_tol=1e-6)
    # the fastest car should have the highest win probability
    assert max(probs.p_win, key=probs.p_win.get) == "A"
    # podium prob >= win prob for every driver
    assert all(probs.p_podium[d] >= probs.p_win[d] - 1e-9 for d in probs.drivers)


def test_plackett_luce_deterministic_seed():
    lap_times = {"A": 90.0, "B": 90.5, "C": 91.0}
    a = calibration.plackett_luce_probabilities(lap_times, n_samples=1000, seed=7)
    b = calibration.plackett_luce_probabilities(lap_times, n_samples=1000, seed=7)
    assert a.p_win == b.p_win


def test_plackett_luce_empty_raises():
    with pytest.raises(ValueError):
        calibration.plackett_luce_probabilities({})


# --------------------------------------------------------------------------- #
# drift — PSI
# --------------------------------------------------------------------------- #


def test_psi_zero_for_identical_distributions():
    xs = [float(i) for i in range(100)]
    assert drift.population_stability_index(xs, xs) == pytest.approx(0.0, abs=1e-9)


def test_psi_positive_for_shifted_distribution():
    base = [float(i) for i in range(100)]
    shifted = [float(i) + 50 for i in range(100)]
    psi = drift.population_stability_index(base, shifted)
    assert psi > 0.25  # large shift -> top severity band
    assert drift.classify_psi(psi) in {"warn", "alarm"}


def test_psi_empty_returns_zero():
    assert drift.population_stability_index([], [1.0, 2.0]) == 0.0


# --------------------------------------------------------------------------- #
# promotion — A/B gate
# --------------------------------------------------------------------------- #


def test_promotion_holds_on_insufficient_overlap():
    prod = [(1, 3.0), (2, 3.1)]
    cand = [(1, 2.0), (2, 2.1)]
    decision = promotion.evaluate_promotion(prod, cand, min_rounds_to_decide=5)
    assert decision.decision == "hold"
    assert "overlap" in decision.reason.lower()


def test_promotion_recommends_clear_improvement():
    # candidate consistently ~30% better over 6 rounds (lower is better)
    prod = [(r, 4.0) for r in range(1, 7)]
    cand = [(r, 2.8) for r in range(1, 7)]
    decision = promotion.evaluate_promotion(prod, cand, min_rounds_to_decide=5)
    assert decision.decision == "promote"
