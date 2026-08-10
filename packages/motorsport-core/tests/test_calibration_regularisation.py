"""Locks the small-sample calibration regularisation (the suite-wide fix).

Raw isotonic on a handful of positive events collapses to a step function: the
top-predicted competitor maps to an over-confident ~1.0 and a long tail maps to
an impossible exact 0.0 (the degeneracy seen across F3/IndyCar/NASCAR). The
calibrator must shrink the isotonic map toward the raw model probability by the
positive-event count and floor every output, so no competitor is ever 0.0 and no
small-sample favourite is ever certain.
"""
from __future__ import annotations

import numpy as np

from motorsport_core.calibration import (
    CALIBRATION_PROB_FLOOR,
    ProbabilityCalibrator,
    StratifiedProbabilityCalibrator,
    _regularise_calibration,
)


def _degenerate_win_history(n_rounds: int, field: int = 25, seed: int = 0):
    """Worst case for isotonic: the single top-predicted driver always wins."""
    rng = np.random.default_rng(seed)
    recs = []
    for _ in range(n_rounds):
        raw = np.sort(rng.uniform(0.005, 0.45, field))[::-1]
        raw = raw / raw.sum()  # Plackett–Luce-like: sums to 1
        for i, p in enumerate(raw):
            recs.append({"market": "win", "predicted": float(p), "observed": int(i == 0)})
    return recs


def test_no_collapse_no_hard_zeros():
    cal = ProbabilityCalibrator().fit_from_history(_degenerate_win_history(11))
    rng = np.random.default_rng(99)
    raw = np.sort(rng.uniform(0.005, 0.45, 25))[::-1]
    raw = raw / raw.sum()
    out = cal.transform("win", raw)
    assert out.min() >= CALIBRATION_PROB_FLOOR - 1e-12, "floor not applied"
    assert (out > 0).all(), "hard-zero probability survived"
    assert out.max() < 0.5, "small-sample favourite collapsed to over-confidence"


def test_shrinkage_increases_with_evidence():
    """More positive events → calibration trusts the empirical fit more, so the
    output moves further from the raw input toward isotonic."""
    rng = np.random.default_rng(1)
    raw = np.sort(rng.uniform(0.005, 0.45, 25))[::-1]
    raw = raw / raw.sum()
    few = ProbabilityCalibrator().fit_from_history(_degenerate_win_history(2))
    many = ProbabilityCalibrator().fit_from_history(_degenerate_win_history(40))
    drift_few = np.abs(few.transform("win", raw) - raw).sum()
    drift_many = np.abs(many.transform("win", raw) - raw).sum()
    assert drift_many > drift_few, "shrinkage should relax as evidence accrues"


def test_regularise_helper_endpoints():
    raw = np.array([0.30, 0.05, 0.0])
    calibrated = np.array([1.0, 0.0, 0.0])  # a fully collapsed isotonic output
    # n_pos=0 → w=0 → pure raw (then floored)
    out0 = _regularise_calibration(raw, calibrated, n_pos=0)
    assert np.allclose(out0[:2], raw[:2])
    assert out0[2] >= CALIBRATION_PROB_FLOOR
    # large n_pos → approaches the calibrated map but still floored (no hard zero)
    out_big = _regularise_calibration(raw, calibrated, n_pos=10_000)
    assert out_big[0] > 0.9
    assert (out_big > 0).all()


def test_stratified_regularised_too():
    recs = _degenerate_win_history(11)
    for r in recs:
        r["stratum"] = "street"
    cal = StratifiedProbabilityCalibrator().fit_from_history(recs)
    rng = np.random.default_rng(7)
    raw = np.sort(rng.uniform(0.005, 0.45, 25))[::-1]
    raw = raw / raw.sum()
    out = cal.transform("win", raw, stratum="street")
    assert (out > 0).all(), "stratified path left a hard zero"
    assert out.max() < 0.5, "stratified path collapsed"
