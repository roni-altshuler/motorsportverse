"""Two-stage classifier + regressor.

Phase 2 roadmap item.  The current Layer 1 model is a single regression
on `AdjustedQualiTime`; it tends to over-shoot rookies (predicts P12
when reality is P19) and under-rate dominant cars (predicts P3 when
reality is P1).  Splitting the prediction into:

    Stage 1 (classifier) → which category does this driver belong to?
                           {top-5, 6-10, 11-15, 16-22}
    Stage 2 (regressor)  → refine within the predicted category

reduces the regressor's working range and tends to help on the tail
buckets.

This module is a scaffold: it can train + predict end-to-end on a
DataFrame, but it is not yet wired into ``export_website_data.py``.
Wire-in is a separate step once the A/B benchmark in
``docs/BENCHMARK_PHASE_1.md`` style shows a material improvement.

Usage
-----

    from models.two_stage import TwoStageRanker

    ranker = TwoStageRanker()
    ranker.fit(X_train, y_train_positions)
    predicted_positions = ranker.predict(X_test)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor


_BUCKET_BOUNDARIES = (5, 10, 15, 22)  # inclusive upper bounds


def _position_to_bucket(pos: int) -> int:
    for idx, upper in enumerate(_BUCKET_BOUNDARIES):
        if pos <= upper:
            return idx
    return len(_BUCKET_BOUNDARIES) - 1


def _bucket_to_centre(bucket: int) -> float:
    lower = 1 if bucket == 0 else _BUCKET_BOUNDARIES[bucket - 1] + 1
    upper = _BUCKET_BOUNDARIES[bucket]
    return (lower + upper) / 2.0


@dataclass
class TwoStageRanker:
    """Two-stage classifier + per-bucket regressor.

    Stage 1: a 4-class GBM that maps feature row → bucket id (0..3).
    Stage 2: 4 small GBM regressors (one per bucket) that map feature
    row → finishing position within the bucket.  At predict time the
    classifier picks the bucket and the matching regressor refines.
    """

    classifier: Optional[GradientBoostingClassifier] = None
    regressors: dict[int, GradientBoostingRegressor] = field(default_factory=dict)
    random_state: int = 42

    def fit(self, X: pd.DataFrame, y_positions: np.ndarray) -> "TwoStageRanker":
        y_positions = np.asarray(y_positions, dtype=int)
        if X.shape[0] != y_positions.shape[0]:
            raise ValueError(
                f"X has {X.shape[0]} rows but y_positions has {y_positions.shape[0]}; "
                "they must be row-aligned."
            )
        buckets = np.array([_position_to_bucket(int(p)) for p in y_positions])

        self.classifier = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=3,
            random_state=self.random_state,
        )
        self.classifier.fit(X, buckets)

        for bucket_id in sorted(set(buckets)):
            mask = buckets == bucket_id
            # Need at least 2 samples per bucket for GBR; fall back to
            # a constant prediction otherwise.
            if mask.sum() < 2:
                continue
            reg = GradientBoostingRegressor(
                n_estimators=120,
                learning_rate=0.05,
                max_depth=2,
                random_state=self.random_state,
            )
            reg.fit(X[mask], y_positions[mask])
            self.regressors[int(bucket_id)] = reg
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.classifier is None:
            raise RuntimeError("TwoStageRanker.fit must be called before predict.")
        bucket_pred = self.classifier.predict(X)
        out = np.empty(X.shape[0], dtype=float)
        for i in range(X.shape[0]):
            b = int(bucket_pred[i])
            reg = self.regressors.get(b)
            if reg is None:
                out[i] = _bucket_to_centre(b)
            else:
                out[i] = float(reg.predict(X.iloc[[i]])[0])
        return out

    def predict_buckets(self, X: pd.DataFrame) -> np.ndarray:
        if self.classifier is None:
            raise RuntimeError("TwoStageRanker.fit must be called before predict.")
        return self.classifier.predict(X)
