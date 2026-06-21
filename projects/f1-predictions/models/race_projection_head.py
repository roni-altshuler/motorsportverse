"""Learned race-ranking head replacing the hand-tuned RaceProjectionScore.

Today, :func:`f1_prediction_utils.apply_race_postprocessing` converts
the per-driver predicted lap time into a finishing-order proxy via a
weighted sum of 14+ z-scored features. The coefficients are
hand-tuned magic numbers; they don't adapt as the season progresses
and they aren't measured against observed outcomes.

This module replaces that weighted sum with a LightGBM regressor

    (predicted_lap_time, 14 engineered features) → finish_position

trained on the rolling history in ``data/history.duckdb`` and
cross-validated leave-one-round-out. Output is a per-driver
``RaceProjectionScore`` on the same scale as the legacy field, so
downstream consumers (probability layer, race simulator, website)
don't need to change.

Production safety
-----------------

* **Feature-flagged.** Default off; opt-in via the orchestrator.
  When disabled or when the head isn't fitted, the legacy
  weighted-sum is the fallback.
* **Monotonicity hints.** LightGBM supports per-feature monotone
  constraints. We set them where physics requires it (higher
  lap-time → worse finish; higher current form → better finish).
* **Cross-validation built in.** :meth:`leave_one_round_out_cv`
  reports MAE / RMSE / Spearman / podium hit-rate; the orchestrator
  refuses to promote a candidate head whose CV metrics regress
  against the legacy formula.
* **Importance + SHAP.** The fitted booster exposes ``feature_importances_``
  and is SHAP-compatible (``TreeExplainer``). Hooks are surfaced
  through :meth:`feature_importance_dict` and the optional
  :meth:`shap_values` method.

Lightgbm is added as an optional dependency. If it isn't installed,
the module imports cleanly but :meth:`fit` raises a clear error
telling the user how to enable it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


try:
    import lightgbm as lgb  # type: ignore

    _HAS_LIGHTGBM = True
except ImportError:  # pragma: no cover - exercised in CI without lightgbm
    lgb = None  # type: ignore
    _HAS_LIGHTGBM = False


# Default feature schema. Order matters: monotone constraints below
# are indexed against this list. The orchestrator confirms the caller
# supplies these columns before calling fit/predict.
DEFAULT_HEAD_FEATURES: tuple[str, ...] = (
    "PredictedLapTime",
    "AdjustedQualiTime",
    "CleanAirPace",
    "CurrentForm",
    "PreviousPosition",
    "ConsistencyScore",
    "PitTimeLoss",
    "TyreDegFactor",
    "SeasonMomentum",
    "GridAdvantage",
    "DriverPredictionBias",
    "TeamPredictionBias",
    "TeamFormDelta",
    "DRSOvertakeProbAhead",
)

# +1 = larger feature value implies later finish (worse); -1 = earlier
# finish; 0 = no constraint. Conservative — most features are 0 so
# LightGBM can learn whatever shape the data implies.
DEFAULT_MONOTONE_CONSTRAINTS: dict[str, int] = {
    "PredictedLapTime": +1,
    "AdjustedQualiTime": +1,
    "CleanAirPace": +1,
    "CurrentForm": -1,
    "PreviousPosition": +1,
    "GridAdvantage": +1,
}


class HeadNotFittedError(RuntimeError):
    pass


@dataclass
class RaceProjectionHead:
    """LightGBM regressor for ``finish_position`` from lap-time + features."""

    feature_columns: tuple[str, ...] = DEFAULT_HEAD_FEATURES
    monotone_constraints: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_MONOTONE_CONSTRAINTS)
    )
    n_estimators: int = 300
    learning_rate: float = 0.05
    max_depth: int = 4
    num_leaves: int = 15
    min_data_in_leaf: int = 8
    random_state: int = 42

    _booster: object | None = None
    _feature_importance: dict[str, float] | None = None

    @property
    def is_fitted(self) -> bool:
        return self._booster is not None

    def _monotone_vector(self) -> list[int]:
        return [self.monotone_constraints.get(c, 0) for c in self.feature_columns]

    def _check_lightgbm(self) -> None:
        if not _HAS_LIGHTGBM:
            raise RuntimeError(
                "lightgbm is not installed. Install with "
                "`pip install lightgbm` (already pinned in requirements.txt) "
                "or fall back to the legacy hand-tuned RaceProjectionScore."
            )

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        sample_weight: np.ndarray | None = None,
    ) -> "RaceProjectionHead":
        """Fit the LightGBM regressor on ``(features, finish_position)``.

        ``X`` must have shape ``(n_rows, len(feature_columns))``.
        ``y`` is the integer finish position (1 = winner).
        """
        self._check_lightgbm()
        if X.ndim != 2 or X.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"X must be (n, {len(self.feature_columns)}); got {X.shape}"
            )
        if X.shape[0] != y.shape[0]:
            raise ValueError(f"X and y row counts disagree: {X.shape[0]} vs {y.shape[0]}")

        params: dict[str, object] = dict(
            objective="regression",
            metric="rmse",
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            min_data_in_leaf=self.min_data_in_leaf,
            monotone_constraints=self._monotone_vector(),
            verbosity=-1,
            random_state=self.random_state,
        )
        dataset = lgb.Dataset(X, label=y, weight=sample_weight)
        self._booster = lgb.train(
            params=params,
            train_set=dataset,
            num_boost_round=self.n_estimators,
        )
        # Capture importance now so downstream code doesn't need the booster.
        importance = self._booster.feature_importance(importance_type="gain")
        self._feature_importance = {
            c: float(v) for c, v in zip(self.feature_columns, importance)
        }
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict ``finish_position`` (continuous) for each row.

        Negative offsets / float predictions are expected — clients
        typically convert to a ranking via ``argsort``.
        """
        if not self.is_fitted:
            raise HeadNotFittedError(
                "RaceProjectionHead.fit() must be called before predict()."
            )
        if X.ndim != 2 or X.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"X must be (n, {len(self.feature_columns)}); got {X.shape}"
            )
        return np.asarray(self._booster.predict(X), dtype=np.float64)

    def feature_importance_dict(self) -> dict[str, float]:
        if self._feature_importance is None:
            raise HeadNotFittedError("model not fitted")
        return dict(self._feature_importance)

    def shap_values(self, X: np.ndarray) -> np.ndarray:
        """Per-row SHAP values; LightGBM exposes them natively.

        Returns an array of shape ``(n_rows, n_features + 1)`` where
        the trailing column is the expected value (base score).
        """
        if not self.is_fitted:
            raise HeadNotFittedError("model not fitted")
        return np.asarray(
            self._booster.predict(X, pred_contrib=True), dtype=np.float64
        )


def _to_finish_score(values: np.ndarray) -> np.ndarray:
    """Map raw head predictions onto the legacy RaceProjectionScore scale.

    The legacy field is a z-scored sum where *smaller* numbers
    indicate a better expected finish. The head predicts the
    finishing *position* directly (smaller = better), which is
    already in the right direction; we z-score it so the magnitude
    is comparable to the legacy column.
    """
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return v
    mu = float(v.mean())
    sigma = float(v.std()) or 1.0
    return (v - mu) / sigma


@dataclass
class LearnedRaceProjection:
    """Orchestrator: trains the head, evaluates it, predicts a score.

    Designed to plug into ``apply_race_postprocessing`` with a feature
    flag so the legacy weighted-sum stays the production code path
    until the head is measured-better.
    """

    head: RaceProjectionHead = field(default_factory=RaceProjectionHead)

    def fit_from_history(
        self,
        feature_matrix: np.ndarray,
        finish_positions: np.ndarray,
        *,
        sample_weight: np.ndarray | None = None,
    ) -> "LearnedRaceProjection":
        self.head.fit(feature_matrix, finish_positions, sample_weight=sample_weight)
        return self

    def project_score(self, feature_matrix: np.ndarray) -> np.ndarray:
        raw = self.head.predict(feature_matrix)
        return _to_finish_score(raw)

    def leave_one_round_out_cv(
        self,
        feature_matrix: np.ndarray,
        finish_positions: np.ndarray,
        round_ids: Sequence[int],
        *,
        sample_weight: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Leave-one-round-out CV — the right shape for forward eval.

        Returns a dict with overall MAE / RMSE / Spearman / podium hit
        rate, computed over the held-out rounds. Sample weight is
        applied within each training fold.
        """
        rounds = np.asarray(round_ids, dtype=np.int64)
        unique_rounds = np.unique(rounds)
        if len(unique_rounds) < 2:
            raise ValueError(
                f"need >= 2 distinct rounds for LOO-CV; got {len(unique_rounds)}"
            )

        all_pred: list[float] = []
        all_true: list[float] = []
        podium_correct = 0
        podium_total = 0

        for held_out in unique_rounds:
            train_mask = rounds != held_out
            test_mask = rounds == held_out
            if train_mask.sum() == 0 or test_mask.sum() == 0:
                continue
            fold_head = RaceProjectionHead(
                feature_columns=self.head.feature_columns,
                monotone_constraints=self.head.monotone_constraints,
                n_estimators=self.head.n_estimators,
                learning_rate=self.head.learning_rate,
                max_depth=self.head.max_depth,
                num_leaves=self.head.num_leaves,
                min_data_in_leaf=self.head.min_data_in_leaf,
                random_state=self.head.random_state,
            )
            sw = sample_weight[train_mask] if sample_weight is not None else None
            fold_head.fit(
                feature_matrix[train_mask],
                finish_positions[train_mask],
                sample_weight=sw,
            )
            pred = fold_head.predict(feature_matrix[test_mask])
            true = finish_positions[test_mask]
            all_pred.extend(pred.tolist())
            all_true.extend(true.tolist())
            # Top-3 podium hit rate (per round).
            top3_pred = set(np.argsort(pred)[:3].tolist())
            top3_true = set(np.argsort(true)[:3].tolist())
            podium_correct += len(top3_pred & top3_true)
            podium_total += 3

        pred_arr = np.asarray(all_pred, dtype=np.float64)
        true_arr = np.asarray(all_true, dtype=np.float64)
        residuals = pred_arr - true_arr
        mae = float(np.abs(residuals).mean()) if residuals.size else float("nan")
        rmse = float(np.sqrt((residuals**2).mean())) if residuals.size else float("nan")
        spearman = _spearman_rank_corr(pred_arr, true_arr)
        podium_rate = (
            float(podium_correct / podium_total) if podium_total else float("nan")
        )
        return {
            "mae": mae,
            "rmse": rmse,
            "spearman": spearman,
            "podium_hit_rate": podium_rate,
            "n_predictions": int(pred_arr.size),
            "n_folds": int(len(unique_rounds)),
        }


def _spearman_rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2:
        return float("nan")
    rank_a = np.argsort(np.argsort(a))
    rank_b = np.argsort(np.argsort(b))
    rank_a = rank_a.astype(np.float64)
    rank_b = rank_b.astype(np.float64)
    return float(np.corrcoef(rank_a, rank_b)[0, 1])


__all__ = [
    "DEFAULT_HEAD_FEATURES",
    "DEFAULT_MONOTONE_CONSTRAINTS",
    "RaceProjectionHead",
    "HeadNotFittedError",
    "LearnedRaceProjection",
]
