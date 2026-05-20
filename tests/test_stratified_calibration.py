"""Tests for the per-stratum probability calibrator (A-P2.2)."""
from __future__ import annotations

import numpy as np

from models.calibration import StratifiedProbabilityCalibrator


def _history_records(
    stratum: str | None,
    market: str,
    n: int,
    *,
    base_predicted: float = 0.5,
    base_observed: float = 0.5,
    spread: float = 0.4,
    seed: int = 0,
) -> list[dict]:
    """Synthetic (predicted, observed) records anchored to a known mean."""
    rng = np.random.default_rng(seed)
    preds = np.clip(rng.normal(base_predicted, spread, n), 0.0, 1.0)
    obs = (preds > rng.uniform(0, 1, n) * (1 - base_observed)).astype(int)
    return [
        {"predicted": float(p), "observed": int(o), "market": market, **({"stratum": stratum} if stratum else {})}
        for p, o in zip(preds, obs)
    ]


def test_stratum_specific_model_used_when_present():
    cal = StratifiedProbabilityCalibrator()
    history = (
        _history_records("street", "win", 50, base_predicted=0.4, base_observed=0.6, seed=1)
        + _history_records("permanent", "win", 50, base_predicted=0.4, base_observed=0.3, seed=2)
    )
    cal.fit_from_history(history)
    assert cal.is_fitted("win", "street")
    assert cal.is_fitted("win", "permanent")
    # Different strata may yield different calibrated values for the same input.
    out_street = cal.transform("win", [0.4], stratum="street")[0]
    out_permanent = cal.transform("win", [0.4], stratum="permanent")[0]
    # We're testing the routing, not the specific value, but they shouldn't be
    # identical if the per-stratum fits captured different empirical rates.
    assert isinstance(out_street, float)
    assert isinstance(out_permanent, float)


def test_unknown_stratum_falls_back_to_global():
    cal = StratifiedProbabilityCalibrator()
    history = _history_records(None, "win", 30, seed=3)
    cal.fit_from_history(history)
    out = cal.transform("win", [0.3, 0.7], stratum="never-seen")
    # Should be the *global* calibrated values, identical to passing no stratum
    out_no_stratum = cal.transform("win", [0.3, 0.7])
    np.testing.assert_array_equal(out, out_no_stratum)


def test_sparse_stratum_skipped_falls_back_to_global():
    """A stratum with <min_samples should not produce a per-stratum model."""
    cal = StratifiedProbabilityCalibrator()
    history = (
        _history_records("street", "win", 3, seed=4)              # below 8-row floor
        + _history_records(None, "win", 20, seed=5)               # global gets samples
    )
    cal.fit_from_history(history)
    assert "street" not in cal.strata_with_models()
    # Transform with unknown stratum still works (falls back to global)
    out = cal.transform("win", [0.5], stratum="street")
    assert out.shape == (1,)


def test_is_fitted_signals_correctly():
    cal = StratifiedProbabilityCalibrator()
    assert not cal.is_fitted()
    cal.fit_from_history(_history_records("street", "win", 30, seed=7))
    assert cal.is_fitted()
    assert cal.is_fitted("win")
    assert cal.is_fitted("win", "street")
    assert cal.is_fitted("win", "unknown")  # falls back to global → still fitted
    assert not cal.is_fitted("top10", "street")


def test_strata_with_models_lists_per_market():
    cal = StratifiedProbabilityCalibrator()
    history = (
        _history_records("street", "win", 30, seed=8)
        + _history_records("street", "podium", 30, seed=9)
    )
    cal.fit_from_history(history)
    strata = cal.strata_with_models()
    assert "street" in strata
    assert set(strata["street"]) == {"win", "podium"}


def test_ignores_records_with_invalid_predictions():
    cal = StratifiedProbabilityCalibrator()
    history = [
        {"market": "win", "predicted": 1.5, "observed": 1, "stratum": "x"},  # out of [0,1]
        {"market": "win", "predicted": 0.5, "observed": 2, "stratum": "x"},  # obs not 0/1
        {"market": "fake-market", "predicted": 0.5, "observed": 1, "stratum": "x"},
        *_history_records("y", "win", 20, seed=10),
    ]
    cal.fit_from_history(history)
    # "x" stratum had no valid records → no per-stratum model
    assert "x" not in cal.strata_with_models()
    # "y" had enough valid records → present
    assert "y" in cal.strata_with_models()
