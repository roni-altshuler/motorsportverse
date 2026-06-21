"""Tests for the bootstrap prediction-interval generator (A-P2.3)."""
from __future__ import annotations

import numpy as np
import pytest

from models.intervals import bootstrap_prediction_intervals


def _toy_dataset(n: int = 60, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    y = X @ np.array([1.0, -0.5, 0.25]) + rng.normal(scale=0.1, size=n)
    return X, y


def test_returns_low_and_high_per_inference_row():
    X_train, y_train = _toy_dataset(80)
    X_inf = X_train[:10]
    low, high = bootstrap_prediction_intervals(
        X_train, y_train, X_inf, n_replicas=10, n_estimators=20
    )
    assert low.shape == (10,)
    assert high.shape == (10,)


def test_high_dominates_low_everywhere():
    X_train, y_train = _toy_dataset(80)
    X_inf = X_train[:10]
    low, high = bootstrap_prediction_intervals(
        X_train, y_train, X_inf, n_replicas=15, n_estimators=20
    )
    assert np.all(high >= low)


def test_deterministic_with_same_seed():
    X_train, y_train = _toy_dataset(80)
    X_inf = X_train[:10]
    a_low, a_high = bootstrap_prediction_intervals(
        X_train, y_train, X_inf, n_replicas=10, n_estimators=20, random_state=7
    )
    b_low, b_high = bootstrap_prediction_intervals(
        X_train, y_train, X_inf, n_replicas=10, n_estimators=20, random_state=7
    )
    np.testing.assert_array_equal(a_low, b_low)
    np.testing.assert_array_equal(a_high, b_high)


def test_band_width_is_positive_for_at_least_some_rows():
    """The bootstrap should disagree on at least some rows so the band
    has positive width somewhere — otherwise the intervals are useless."""
    X_train, y_train = _toy_dataset(60)
    X_inf = X_train[:20]
    low, high = bootstrap_prediction_intervals(
        X_train, y_train, X_inf, n_replicas=15, n_estimators=20
    )
    assert np.any((high - low) > 0)


def test_rejects_too_few_training_rows():
    with pytest.raises(ValueError, match="training rows"):
        bootstrap_prediction_intervals(
            np.zeros((3, 2)), np.zeros(3), np.zeros((2, 2)),
            n_replicas=5, n_estimators=20,
        )


def test_rejects_n_replicas_below_two():
    X_train, y_train = _toy_dataset(40)
    with pytest.raises(ValueError, match="n_replicas"):
        bootstrap_prediction_intervals(
            X_train, y_train, X_train[:5],
            n_replicas=1, n_estimators=20,
        )


def test_empty_inference_returns_empty_arrays():
    X_train, y_train = _toy_dataset(40)
    low, high = bootstrap_prediction_intervals(
        X_train, y_train, np.zeros((0, 3)),
        n_replicas=5, n_estimators=20,
    )
    assert low.shape == (0,)
    assert high.shape == (0,)
