"""Race-grouped chronological cross-validation.

Why this exists
---------------
The existing pipeline used ``sklearn.model_selection.train_test_split``
with a random per-driver split, which silently leaks signal across the
time axis: a driver's late-season 2025 lap can land in training while
their early-season 2024 lap lands in the held-out test, and the same race
can have rows on both sides of the split. That gives optimistic offline
metrics that don't survive the first real race.

``RaceGroupedTimeSeriesSplit`` fixes both problems at once:

  * **Race grouped**: every row of a given (season, round) belongs to
    exactly one fold. A race is never split between train and test.
  * **Chronological**: folds advance forward in time. Fold N is trained
    on rounds strictly before its test rounds.

This matches the production task — predicting an upcoming race using
only data that existed before it — and is the only honest way to score
the new LambdaRank pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RaceGroupedTimeSeriesSplit:
    """Chronological CV splitter that respects race-level groups.

    Parameters
    ----------
    n_splits :
        Number of (train, test) folds to emit. The first fold trains on
        ``min_train_races`` and tests on the next ``test_size_races``;
        subsequent folds extend the training window by ``test_size_races``
        races each (expanding-window) or by ``test_size_races`` while
        rolling the training start forward (sliding window).
    min_train_races :
        Minimum number of distinct races (each ``(season, round)`` tuple)
        in the very first training window.
    test_size_races :
        How many races to put in each test fold.
    gap_races :
        Number of races to skip between the train and test windows of
        each fold. Defaults to 0; setting > 0 leaves a buffer for
        feature-lag effects.
    expanding :
        If True (default), the training window grows fold over fold. If
        False, the training window slides forward keeping a fixed width
        of ``min_train_races``.

    Notes
    -----
    * Groups are derived from a frame containing ``Season`` and ``Round``
      columns, or from a ``(season, round)`` array passed via the
      ``groups`` argument of :meth:`split`.
    * The splitter is deterministic given the input ordering.
    """

    n_splits: int = 5
    min_train_races: int = 30
    test_size_races: int = 4
    gap_races: int = 0
    expanding: bool = True

    def _race_keys(self, groups: Iterable) -> np.ndarray:
        """Coerce an arbitrary groups-shaped argument to a ``(N, 2)`` int array
        of ``(season, round)`` keys."""
        if isinstance(groups, pd.DataFrame):
            arr = groups[["Season", "Round"]].to_numpy()
        elif isinstance(groups, pd.Series):
            arr = np.asarray(groups.tolist())
        else:
            arr = np.asarray(groups)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError(
                f"groups must be a 2-column array of (season, round); got shape {arr.shape}"
            )
        return arr.astype(np.int64)

    def split(
        self,
        X,  # noqa: N803 — sklearn-style parameter naming
        y=None,
        groups: Iterable | None = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Yield ``(train_idx, test_idx)`` per fold.

        ``groups`` is required and must be 1:1 with rows in ``X``. Pass a
        DataFrame with ``Season``/``Round`` columns, or an ``(N, 2)`` array.
        """
        if groups is None:
            raise ValueError("groups is required (Season/Round per row)")
        keys = self._race_keys(groups)
        n_rows = keys.shape[0]
        if y is not None and len(y) != n_rows:
            raise ValueError(f"groups has {n_rows} rows but y has {len(y)}")

        # Sort distinct race keys chronologically.
        unique_races = np.unique(keys, axis=0)
        # Sort by season*100 + round so order survives mixed seasons cleanly.
        order = np.lexsort((unique_races[:, 1], unique_races[:, 0]))
        chrono = unique_races[order]
        n_races = len(chrono)

        if n_races < self.min_train_races + self.test_size_races:
            raise ValueError(
                f"Not enough distinct races ({n_races}) for "
                f"min_train_races={self.min_train_races} + "
                f"test_size_races={self.test_size_races}"
            )

        for fold in range(self.n_splits):
            test_start = self.min_train_races + fold * self.test_size_races
            test_end = test_start + self.test_size_races
            if test_end > n_races:
                # Truncate or stop early — emit a smaller final test if any room.
                if test_start >= n_races:
                    break
                test_end = n_races

            train_start = 0 if self.expanding else fold * self.test_size_races
            train_end = max(0, test_start - self.gap_races)

            train_races = chrono[train_start:train_end]
            test_races = chrono[test_start:test_end]

            if len(train_races) == 0 or len(test_races) == 0:
                continue

            train_mask = _membership_mask(keys, train_races)
            test_mask = _membership_mask(keys, test_races)

            train_idx = np.where(train_mask)[0]
            test_idx = np.where(test_mask)[0]
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue
            yield train_idx, test_idx

    def get_n_splits(self, X=None, y=None, groups=None) -> int:  # noqa: ARG002
        return self.n_splits


def _membership_mask(keys: np.ndarray, races: np.ndarray) -> np.ndarray:
    """Vectorised: is each row in ``keys`` a member of ``races``?"""
    # Encode each (season, round) tuple as a single int for set ops
    enc_keys = keys[:, 0].astype(np.int64) * 100_000 + keys[:, 1].astype(np.int64)
    enc_races = races[:, 0].astype(np.int64) * 100_000 + races[:, 1].astype(np.int64)
    return np.isin(enc_keys, enc_races)
