"""Tests for ``models/cv.py::RaceGroupedTimeSeriesSplit``.

The two invariants that the splitter exists to guarantee:

  1. A race (one (season, round) tuple) is **never split** between train
     and test. If row X is in train, every other row from the same race
     is also in train.
  2. Test folds are **chronologically after** their train folds. No row
     in test can come from a race earlier than the max train race.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.cv import RaceGroupedTimeSeriesSplit


def _synthetic_history(n_seasons: int = 3, races_per_season: int = 20, drivers: int = 20) -> pd.DataFrame:
    rows = []
    for s in range(2022, 2022 + n_seasons):
        for r in range(1, races_per_season + 1):
            for d in range(drivers):
                rows.append({"Season": s, "Round": r, "Driver": f"D{d:02d}",
                             "FinishPosition": (d + r) % drivers + 1, "f": float(s * 100 + r + d)})
    return pd.DataFrame(rows)


def test_split_respects_race_groups():
    df = _synthetic_history()
    splitter = RaceGroupedTimeSeriesSplit(n_splits=3, min_train_races=20, test_size_races=4)
    for train_idx, test_idx in splitter.split(df[["f"]], df["FinishPosition"], groups=df):
        train_races = set(map(tuple, df.iloc[train_idx][["Season", "Round"]].values.tolist()))
        test_races = set(map(tuple, df.iloc[test_idx][["Season", "Round"]].values.tolist()))
        # No race appears in both
        assert train_races.isdisjoint(test_races), (
            f"race leaked across split: {train_races & test_races}"
        )


def test_split_is_chronological():
    df = _synthetic_history()
    splitter = RaceGroupedTimeSeriesSplit(n_splits=3, min_train_races=20, test_size_races=4)
    for train_idx, test_idx in splitter.split(df[["f"]], df["FinishPosition"], groups=df):
        train_keys = df.iloc[train_idx][["Season", "Round"]]
        test_keys = df.iloc[test_idx][["Season", "Round"]]
        max_train = (train_keys["Season"] * 100 + train_keys["Round"]).max()
        min_test = (test_keys["Season"] * 100 + test_keys["Round"]).min()
        assert max_train < min_test, (
            f"non-chronological: train extends to {max_train}, test starts at {min_test}"
        )


def test_split_emits_requested_fold_count():
    df = _synthetic_history()
    splitter = RaceGroupedTimeSeriesSplit(n_splits=3, min_train_races=20, test_size_races=4)
    folds = list(splitter.split(df[["f"]], df["FinishPosition"], groups=df))
    assert len(folds) == 3


def test_split_raises_when_not_enough_races():
    df = _synthetic_history(n_seasons=1, races_per_season=10)
    splitter = RaceGroupedTimeSeriesSplit(n_splits=3, min_train_races=20, test_size_races=4)
    with pytest.raises(ValueError, match="Not enough distinct races"):
        list(splitter.split(df[["f"]], df["FinishPosition"], groups=df))


def test_split_rejects_missing_groups():
    splitter = RaceGroupedTimeSeriesSplit()
    with pytest.raises(ValueError, match="groups is required"):
        list(splitter.split(np.zeros((10, 1))))


def test_get_n_splits_matches_config():
    splitter = RaceGroupedTimeSeriesSplit(n_splits=7)
    assert splitter.get_n_splits() == 7
