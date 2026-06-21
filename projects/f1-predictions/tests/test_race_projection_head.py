"""Tests for the LightGBM-based RaceProjectionHead."""
from __future__ import annotations

import numpy as np
import pytest

try:
    import lightgbm  # noqa: F401

    _HAS_LIGHTGBM = True
except ImportError:
    _HAS_LIGHTGBM = False

from models.race_projection_head import (
    DEFAULT_HEAD_FEATURES,
    HeadNotFittedError,
    LearnedRaceProjection,
    RaceProjectionHead,
)


needs_lgb = pytest.mark.skipif(not _HAS_LIGHTGBM, reason="lightgbm not installed")


def _synthetic_dataset(
    n_rows: int = 200,
    n_rounds: int = 10,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n_rows, len(DEFAULT_HEAD_FEATURES)))
    # Make finish position lightly correlated with the first column
    # (PredictedLapTime): higher pace → worse finish.
    finish = (X[:, 0] * 0.6 + rng.normal(scale=0.4, size=n_rows)).argsort().argsort()
    finish = finish + 1
    rounds = np.tile(np.arange(1, n_rounds + 1), n_rows // n_rounds + 1)[:n_rows]
    return X, finish.astype(np.float64), rounds


def test_predict_before_fit_raises():
    head = RaceProjectionHead()
    with pytest.raises(HeadNotFittedError):
        head.predict(np.zeros((1, len(DEFAULT_HEAD_FEATURES))))


@needs_lgb
def test_fit_and_predict_round_trip():
    X, y, _ = _synthetic_dataset()
    head = RaceProjectionHead(n_estimators=40).fit(X, y)
    preds = head.predict(X)
    assert preds.shape == y.shape


@needs_lgb
def test_feature_importance_populated_after_fit():
    X, y, _ = _synthetic_dataset()
    head = RaceProjectionHead(n_estimators=40).fit(X, y)
    importance = head.feature_importance_dict()
    assert set(importance.keys()) == set(DEFAULT_HEAD_FEATURES)
    assert sum(importance.values()) > 0


@needs_lgb
def test_shape_validation_on_predict():
    X, y, _ = _synthetic_dataset()
    head = RaceProjectionHead(n_estimators=20).fit(X, y)
    with pytest.raises(ValueError, match="must be"):
        head.predict(np.zeros((5, 3)))


@needs_lgb
def test_learned_projection_score_centered():
    X, y, _ = _synthetic_dataset()
    learned = LearnedRaceProjection()
    learned.fit_from_history(X, y)
    scores = learned.project_score(X)
    assert scores.shape == y.shape
    # z-scored output: mean ≈ 0, std ≈ 1.
    assert abs(scores.mean()) < 1e-6
    assert abs(scores.std() - 1.0) < 1e-6


@needs_lgb
def test_leave_one_round_out_cv_reports_metrics():
    X, y, rounds = _synthetic_dataset(n_rows=120, n_rounds=6)
    learned = LearnedRaceProjection(head=RaceProjectionHead(n_estimators=40))
    metrics = learned.leave_one_round_out_cv(X, y, rounds)
    assert {"mae", "rmse", "spearman", "podium_hit_rate"} <= set(metrics.keys())
    assert metrics["n_folds"] == 6
    assert metrics["n_predictions"] == 120
    assert 0.0 <= metrics["podium_hit_rate"] <= 1.0


@needs_lgb
def test_loo_cv_rejects_single_round():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20, len(DEFAULT_HEAD_FEATURES)))
    y = np.arange(20).astype(np.float64)
    rounds = np.ones(20, dtype=np.int64)
    learned = LearnedRaceProjection()
    with pytest.raises(ValueError, match=">= 2 distinct rounds"):
        learned.leave_one_round_out_cv(X, y, rounds)


@needs_lgb
def test_monotone_constraints_passed_through_with_default_features():
    head = RaceProjectionHead()
    assert head._monotone_vector()[0] == +1  # PredictedLapTime
