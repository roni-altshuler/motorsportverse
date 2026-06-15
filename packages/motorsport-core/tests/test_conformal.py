"""Tests for split conformal prediction intervals."""
from __future__ import annotations

import numpy as np
import pytest

from motorsport_core.conformal import (
    ConformalIntervals,
    StratifiedConformal,
    split_conformal_quantile,
    width_to_confidence_label,
)


def _normal_residuals(n: int = 200, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    yhat = rng.normal(loc=92.0, scale=1.5, size=n)
    y = yhat + rng.normal(loc=0.0, scale=0.5, size=n)
    return y, yhat


def test_quantile_strictly_increases_with_more_extreme_residuals():
    base = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    extreme = np.array([0.1, 0.2, 0.3, 0.4, 5.0])
    assert split_conformal_quantile(base, alpha=0.1) < split_conformal_quantile(
        extreme, alpha=0.1
    )


def test_quantile_rejects_alpha_out_of_range():
    with pytest.raises(ValueError, match="alpha"):
        split_conformal_quantile([0.1, 0.2], alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        split_conformal_quantile([0.1, 0.2], alpha=1.5)


def test_conformal_fit_and_predict_intervals():
    y, yhat = _normal_residuals(200, seed=11)
    conf = ConformalIntervals(alpha=0.1).fit(y[:140], yhat[:140])
    lo, hi = conf.predict_intervals(yhat[140:])
    assert lo.shape == hi.shape == (60,)
    assert np.all(hi >= lo)
    # The interval width equals 2 * q for every row (symmetric).
    np.testing.assert_array_almost_equal(hi - lo, conf.width())


def test_conformal_coverage_close_to_target():
    # With 1k samples and a moderate residual distribution, 90% target
    # should hold to within ±3%.
    y, yhat = _normal_residuals(1000, seed=7)
    conf = ConformalIntervals(alpha=0.10).fit(y[:700], yhat[:700])
    lo, hi = conf.predict_intervals(yhat[700:])
    in_band = ((y[700:] >= lo) & (y[700:] <= hi)).mean()
    assert 0.85 <= in_band <= 0.95


def test_conformal_predict_requires_fit():
    with pytest.raises(RuntimeError, match="fit"):
        ConformalIntervals().predict_intervals([1.0, 2.0])


def test_conformal_rejects_undersized_calibration_set():
    y = np.zeros(3)
    yhat = np.zeros(3)
    with pytest.raises(ValueError, match=">="):
        ConformalIntervals().fit(y, yhat)


def test_stratified_falls_back_to_global_for_sparse_strata():
    y, yhat = _normal_residuals(120, seed=3)
    strata = ["dry"] * 100 + ["wet"] * 20
    cal = StratifiedConformal(alpha=0.1, min_samples_per_stratum=30).fit(
        y, yhat, strata
    )
    # Wet stratum (20 rows) should be missing → fall back to global.
    assert "wet" not in cal.stratum_coverage()
    assert "dry" in cal.stratum_coverage()
    lo, hi = cal.predict_intervals(yhat[:5], ["wet"] * 5)
    # The intervals are valid (lower < upper).
    assert np.all(hi > lo)


def test_stratified_uses_per_stratum_width_when_populated():
    rng = np.random.default_rng(0)
    n = 200
    yhat_dry = rng.normal(scale=0.3, size=n) + 92.0
    y_dry = yhat_dry + rng.normal(scale=0.3, size=n)
    yhat_wet = rng.normal(scale=2.0, size=n) + 92.0
    y_wet = yhat_wet + rng.normal(scale=2.0, size=n)
    y = np.concatenate([y_dry, y_wet])
    yhat = np.concatenate([yhat_dry, yhat_wet])
    strata = ["dry"] * n + ["wet"] * n
    cal = StratifiedConformal(alpha=0.1, min_samples_per_stratum=10).fit(
        y, yhat, strata
    )
    lo_dry, hi_dry = cal.predict_intervals([92.0], ["dry"])
    lo_wet, hi_wet = cal.predict_intervals([92.0], ["wet"])
    # Wet stratum should produce noticeably wider intervals.
    assert (hi_wet[0] - lo_wet[0]) > (hi_dry[0] - lo_dry[0])


def test_width_to_confidence_label_buckets():
    labels = width_to_confidence_label([1.0, 2.0, 3.0, 4.0, 5.0])
    # Smallest gets High, largest gets Low, middle gets Medium.
    assert labels[0] == "High"
    assert labels[-1] == "Low"
    assert "Medium" in labels
