"""Smoke tests for ``models/ranking.py::LambdaRanker``.

These tests exercise the input/output contract on tiny synthetic data so
the wrapper stays honest about LightGBM's group-array conventions. Full
hyperparameter behaviour is covered by ``scripts/tune_ranker.py`` and the
forward-eval harness.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

lgb = pytest.importorskip("lightgbm")  # noqa: F841

from models.ranking import LambdaRanker, LambdaRankerConfig, build_groups  # noqa: E402


def _synthetic_races(n_races: int = 6, drivers: int = 8) -> pd.DataFrame:
    """Construct contiguous race-grouped rows. The 'pace' feature is
    designed to correlate with finishing position so the ranker has
    something to learn."""
    rows = []
    for r in range(1, n_races + 1):
        for d in range(drivers):
            pace = d + np.random.default_rng(r * 100 + d).normal(0, 0.4)
            rows.append({
                "Season": 2025,
                "Round": r,
                "Driver": f"D{d:02d}",
                "pace": pace,
                "FinishPosition": d + 1,
            })
    return pd.DataFrame(rows)


def test_build_groups_returns_contiguous_counts():
    df = _synthetic_races(n_races=3, drivers=4)
    groups = build_groups(df)
    # 3 races × 4 drivers each
    assert list(groups) == [4, 4, 4]
    assert int(groups.sum()) == len(df)


def test_lambdaranker_fit_predict_roundtrip():
    df = _synthetic_races(n_races=6, drivers=8)
    X = df[["pace"]]
    y = df["FinishPosition"].values
    groups = build_groups(df)
    ranker = LambdaRanker(config=LambdaRankerConfig(
        num_boost_round=80, early_stopping_rounds=0, verbose=-1,
    ))
    ranker.fit(X, y, groups)
    preds = ranker.predict(X)
    assert preds.shape == (len(X),)
    positions = ranker.rank_predictions(X, groups)
    # Each race's positions are a permutation of 1..drivers
    start = 0
    for size in groups.astype(int):
        end = start + size
        assert sorted(positions[start:end].tolist()) == list(range(1, size + 1))
        start = end


def test_rank_predictions_orders_by_score_desc():
    df = pd.DataFrame({
        "Season": [2025] * 4, "Round": [1] * 4,
        "Driver": list("ABCD"),
        "pace": [3.0, 2.0, 1.0, 0.0],
        "FinishPosition": [4, 3, 2, 1],
    })
    X = df[["pace"]]
    y = df["FinishPosition"].values
    groups = build_groups(df)
    ranker = LambdaRanker(config=LambdaRankerConfig(
        num_boost_round=40, early_stopping_rounds=0, verbose=-1,
    ))
    ranker.fit(X, y, groups)
    # Higher score → predicted to finish earlier (P1).
    scores = ranker.predict(X)
    positions = ranker.rank_predictions(X, groups)
    # The driver with the highest score should get P1
    assert positions[int(np.argmax(scores))] == 1
