"""LightGBM LambdaRank wrapper for race-finishing-position prediction.

Why this exists
---------------
The legacy ensemble regresses on lap times and then runs a hand-tuned
``RaceProjectionScore`` post-processor to produce a finishing order. This
is two layers of error stacking — the regressor optimises MAE in seconds,
not ranking quality, and the post-processor weights are tuned by hand
against a small benchmark set. Lap-time MAE of 0.15 s leaves easy podium
swaps on the table because the loss can't see them.

A direct learning-to-rank objective (LambdaRank / NDCG) fits the
actual problem: given a race of 22 drivers, output a score per driver
such that the highest-scored driver is the one we predict will finish
first. Pairwise gradients pull drivers we ranked too low above drivers we
ranked too high, weighted by how much that swap improves NDCG@K.

We keep this behind a feature flag in ``train_ensemble(model_kind=...)``
so the existing pipeline keeps shipping live predictions while the
ranker runs as a shadow stream under ``models/promotion.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
except ImportError as exc:  # pragma: no cover — listed in requirements.txt
    raise RuntimeError(
        "lightgbm is required for models/ranking.py. Install with `pip install lightgbm`."
    ) from exc


def build_groups(season_round: pd.DataFrame, sprint_col: str | None = "IsSprint") -> np.ndarray:
    """Compute LightGBM ``group`` array (row counts per query) for race grouping.

    The frame must be sorted such that all rows of one ``(season, round, sprint)``
    triple are contiguous. The sprint flag, when present, splits the sprint
    and main race rows into separate ranking queries — they have different
    weather/strategy regimes and shouldn't compete in the same loss group.
    """
    cols = ["Season", "Round"]
    if sprint_col and sprint_col in season_round.columns:
        cols.append(sprint_col)
    keys = season_round[cols].astype("Int64").fillna(0).to_numpy()
    # Confirm contiguity — LightGBM requires it.
    if len(keys) == 0:
        return np.zeros(0, dtype=np.int64)
    changes = np.any(keys[1:] != keys[:-1], axis=1)
    boundaries = np.concatenate(([0], np.where(changes)[0] + 1, [len(keys)]))
    counts = np.diff(boundaries)
    return counts.astype(np.int64)


@dataclass
class LambdaRankerConfig:
    """Hyperparameters with sensible defaults. Tune via ``scripts/tune_ranker.py``."""

    objective: str = "lambdarank"
    metric: tuple[str, ...] = ("ndcg",)
    eval_at: tuple[int, ...] = (3, 5, 10)
    lambdarank_truncation_level: int = 10
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_data_in_leaf: int = 20
    feature_fraction: float = 0.9
    bagging_fraction: float = 0.9
    bagging_freq: int = 5
    max_depth: int = -1
    num_boost_round: int = 800
    early_stopping_rounds: int = 50
    seed: int = 1337
    verbose: int = -1

    def to_lgb_params(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "metric": list(self.metric),
            "eval_at": list(self.eval_at),
            "lambdarank_truncation_level": self.lambdarank_truncation_level,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "min_data_in_leaf": self.min_data_in_leaf,
            "feature_fraction": self.feature_fraction,
            "bagging_fraction": self.bagging_fraction,
            "bagging_freq": self.bagging_freq,
            "max_depth": self.max_depth,
            "seed": self.seed,
            "verbose": self.verbose,
        }


@dataclass
class LambdaRanker:
    """Thin wrapper around ``lgb.train`` for ranking.

    Target convention: lower is better (finishing position 1 = winner).
    LambdaRank expects higher = better, so we map ``relevance = 22 - finish``
    inside ``fit`` to invert the polarity. Predictions retain the
    "higher = predicted-to-finish-higher" convention; ``rank_predictions``
    turns them back into 1..22 finishing positions.
    """

    config: LambdaRankerConfig = field(default_factory=LambdaRankerConfig)
    booster: lgb.Booster | None = None
    feature_names: list[str] | None = None

    def fit(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        groups: np.ndarray,
        *,
        eval_set: tuple[pd.DataFrame, np.ndarray, np.ndarray] | None = None,
    ) -> "LambdaRanker":
        if len(X) != len(y) or len(X) != int(groups.sum()):
            raise ValueError(
                f"shape mismatch: X={len(X)}, y={len(y)}, sum(groups)={int(groups.sum())}"
            )
        self.feature_names = list(X.columns)

        relevance = _to_relevance(y)
        train_set = lgb.Dataset(
            X.values,
            label=relevance,
            group=groups,
            feature_name=self.feature_names,
            free_raw_data=False,
        )
        valid_sets = [train_set]
        valid_names = ["train"]
        if eval_set is not None:
            eX, ey, eg = eval_set
            valid_sets.append(
                lgb.Dataset(
                    eX.values,
                    label=_to_relevance(ey),
                    group=eg,
                    feature_name=list(eX.columns),
                    free_raw_data=False,
                    reference=train_set,
                )
            )
            valid_names.append("valid")

        callbacks: list[Any] = []
        if self.config.early_stopping_rounds and eval_set is not None:
            callbacks.append(
                lgb.early_stopping(
                    stopping_rounds=self.config.early_stopping_rounds,
                    verbose=False,
                )
            )
        callbacks.append(lgb.log_evaluation(period=0))

        self.booster = lgb.train(
            self.config.to_lgb_params(),
            train_set,
            num_boost_round=self.config.num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.booster is None:
            raise RuntimeError("LambdaRanker has not been fit yet")
        if self.feature_names is not None:
            X = X[self.feature_names]
        return self.booster.predict(X.values)

    def rank_predictions(
        self,
        X: pd.DataFrame,
        groups: np.ndarray,
    ) -> np.ndarray:
        """Return integer finishing positions (1 = winner) per row, grouped."""
        raw = self.predict(X)
        positions = np.empty_like(raw, dtype=np.int64)
        start = 0
        for size in groups.astype(int):
            end = start + size
            slice_scores = raw[start:end]
            order = np.argsort(-slice_scores)  # descending → P1 first
            rank = np.empty(size, dtype=np.int64)
            rank[order] = np.arange(1, size + 1)
            positions[start:end] = rank
            start = end
        return positions


def _to_relevance(y: Iterable[float]) -> np.ndarray:
    """Map finishing positions (1..N, lower = better) to LightGBM relevance
    (higher = better). Caps at 22 so DNFs sit at relevance 0."""
    arr = np.asarray(list(y), dtype=np.float64)
    capped = np.clip(arr, 1.0, 22.0)
    return (22.0 - capped + 1.0).astype(np.int32)  # P1 → 22, P22 → 1
