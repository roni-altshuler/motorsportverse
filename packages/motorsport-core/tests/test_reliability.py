"""Tests for reliability / ECE / MCE / Brier helpers."""
from __future__ import annotations

import numpy as np
import pytest

from motorsport_core.reliability import (
    brier_score,
    compute_calibration_metrics,
    compute_market_report_from_probabilities,
    expected_calibration_error,
    maximum_calibration_error,
    metrics_to_dict,
    reliability_bins,
    save_reliability_diagram,
)


def _perfect_calibration_data(n: int = 200, seed: int = 1):
    rng = np.random.default_rng(seed)
    p = rng.uniform(0, 1, size=n)
    y = rng.binomial(1, p)
    return p, y


def test_brier_score_zero_for_perfect_predictions():
    p = np.array([0.0, 1.0, 0.0, 1.0])
    y = np.array([0, 1, 0, 1])
    assert brier_score(p, y) == pytest.approx(0.0)


def test_brier_score_known_value():
    p = np.array([0.5, 0.5])
    y = np.array([0, 1])
    # Each row contributes 0.25; mean = 0.25.
    assert brier_score(p, y) == pytest.approx(0.25)


def test_reliability_bins_shape():
    p, y = _perfect_calibration_data(500)
    bins = reliability_bins(p, y, n_bins=10)
    assert len(bins) == 10
    # Bins partition [0, 1].
    assert bins[0].lower == 0.0
    assert bins[-1].upper == 1.0


def test_ece_smaller_for_well_calibrated_than_skewed():
    rng = np.random.default_rng(0)
    n = 1000
    p_good = rng.uniform(0, 1, size=n)
    y_good = rng.binomial(1, p_good)
    p_bad = np.full(n, 0.9)
    y_bad = rng.binomial(1, 0.3, size=n)
    good = compute_calibration_metrics(p_good, y_good)
    bad = compute_calibration_metrics(p_bad, y_bad)
    assert good.ece < bad.ece
    assert good.brier < bad.brier


def test_ece_within_unit_interval():
    p, y = _perfect_calibration_data(500)
    bins = reliability_bins(p, y)
    ece = expected_calibration_error(bins)
    mce = maximum_calibration_error(bins)
    assert 0.0 <= ece <= 1.0
    assert 0.0 <= mce <= 1.0
    # MCE >= ECE by definition.
    assert mce >= ece - 1e-9


def test_metrics_to_dict_is_json_serialisable():
    p, y = _perfect_calibration_data(50)
    m = compute_calibration_metrics(p, y)
    payload = metrics_to_dict(m)
    import json
    json.dumps(payload)  # must not raise


def test_market_report_skips_mismatched_lengths():
    preds = {"win": [0.1, 0.2, 0.3], "podium": [0.4, 0.5]}
    outs = {"win": [0, 1, 0], "podium": [1, 0, 1]}  # podium length differs
    report = compute_market_report_from_probabilities(preds, outs)
    assert "win" in report.by_market
    assert "podium" not in report.by_market


def test_save_reliability_diagram_writes_png(tmp_path):
    pytest.importorskip("matplotlib")  # plotting is an optional extra for core
    p, y = _perfect_calibration_data(200)
    metrics = compute_calibration_metrics(p, y)
    out = save_reliability_diagram(metrics, tmp_path / "reliability.png", title="test")
    assert out.exists()
    assert out.stat().st_size > 0


def test_shape_mismatch_raises():
    with pytest.raises(ValueError, match="shape"):
        brier_score([0.1, 0.2], [1])
    with pytest.raises(ValueError, match="shape"):
        reliability_bins([0.1, 0.2], [1])
