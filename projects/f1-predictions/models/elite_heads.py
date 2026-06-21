"""Podium and winner classifier heads.

Two binary classifiers on top of the elite-signal features:

* :class:`PodiumHead` — P(driver finishes P1-P3).
* :class:`WinnerHead` — P(driver finishes P1).

Both expose ``fit``, ``predict_proba``, ``save``, ``load``. We default
to :class:`sklearn.linear_model.LogisticRegression` with
``class_weight='balanced'`` because the positive class is small
(podium ~14%, winner ~5%) and a small-data linear model is robust. A
``GradientBoostingClassifier`` alternative is available for cases
where a richer feature interaction would help (selected by passing
``estimator="gbm"`` to ``fit``).

Training protocol (per the task brief):

* Train on 2024 only.
* Evaluate on 2025.
* Report AUC, Brier, precision@k (k=3 for podium, k=1 for winner).
* Save artefacts to ``models/registry/elite_heads/``.

Feature columns are pulled from
:mod:`models.elite_features.FEATURE_COLUMNS`. Missing values are
mean-imputed at train time (early-season rows with thin priors); the
classifier sees a fully-populated feature matrix.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.elite_features import FEATURE_COLUMNS


EstimatorKind = Literal["logreg", "gbm"]


def _make_pipeline(estimator: EstimatorKind, random_state: int) -> Pipeline:
    if estimator == "logreg":
        clf = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            solver="lbfgs",
            random_state=random_state,
        )
    elif estimator == "gbm":
        clf = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            random_state=random_state,
        )
    else:
        raise ValueError(f"unknown estimator {estimator!r}")
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("clf", clf),
        ]
    )


@dataclass
class _BinaryHead:
    """Shared logic for podium / winner heads."""

    target_max_position: int  # ≤ this counts as positive
    estimator: EstimatorKind = "logreg"
    random_state: int = 42
    feature_columns: Sequence[str] = field(default=FEATURE_COLUMNS)
    pipeline: Pipeline | None = None

    def _y_from_actual(self, actual_position: pd.Series) -> np.ndarray:
        return (actual_position <= self.target_max_position).astype(int).to_numpy()

    def fit(
        self, feats_df: pd.DataFrame, actual_position: pd.Series
    ) -> "_BinaryHead":
        """Fit the classifier.

        feats_df must contain ``self.feature_columns``. ``actual_position`` is
        row-aligned. Rows where actual_position is NaN are dropped.
        """
        if actual_position.isna().any():
            mask = ~actual_position.isna()
            feats_df = feats_df.loc[mask].reset_index(drop=True)
            actual_position = actual_position.loc[mask].reset_index(drop=True)
        X = feats_df[list(self.feature_columns)].to_numpy(dtype=float)
        y = self._y_from_actual(actual_position)
        if len(np.unique(y)) < 2:
            raise ValueError(
                f"only one class present in y for target<=P{self.target_max_position};"
                " cannot train a classifier"
            )
        self.pipeline = _make_pipeline(self.estimator, self.random_state)
        self.pipeline.fit(X, y)
        return self

    def predict_proba(self, feats_df: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("call fit() before predict_proba()")
        X = feats_df[list(self.feature_columns)].to_numpy(dtype=float)
        probs = self.pipeline.predict_proba(X)
        # Column 1 is P(positive class) since the imputer/scaler don't shuffle
        # class order; verify defensively.
        clf = self.pipeline.named_steps["clf"]
        classes = list(clf.classes_)
        pos_idx = classes.index(1) if 1 in classes else len(classes) - 1
        return probs[:, pos_idx]

    def feature_importance(self) -> dict[str, float]:
        """Return per-feature importance, normalised to sum to 1.

        For LogisticRegression: absolute value of standardised coefficients.
        For GradientBoosting: built-in feature_importances_.
        """
        if self.pipeline is None:
            raise RuntimeError("call fit() before feature_importance()")
        clf = self.pipeline.named_steps["clf"]
        if isinstance(clf, LogisticRegression):
            coefs = np.abs(clf.coef_[0])
        elif isinstance(clf, GradientBoostingClassifier):
            coefs = clf.feature_importances_
        else:
            coefs = np.zeros(len(self.feature_columns))
        total = coefs.sum()
        if total <= 0:
            return {name: 0.0 for name in self.feature_columns}
        return {
            name: float(c / total)
            for name, c in zip(self.feature_columns, coefs)
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "target_max_position": self.target_max_position,
                "estimator": self.estimator,
                "feature_columns": list(self.feature_columns),
                "random_state": self.random_state,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "_BinaryHead":
        blob = joblib.load(path)
        # PodiumHead/WinnerHead override __init__ to hardcode target_max_position,
        # so we can't pass it. Reconstruct via __new__ + manual attr set so the
        # call works for both the subclass and the base.
        head = cls.__new__(cls)
        _BinaryHead.__init__(
            head,
            target_max_position=int(blob["target_max_position"]),
            estimator=blob.get("estimator", "logreg"),
            random_state=int(blob.get("random_state", 42)),
            feature_columns=tuple(blob.get("feature_columns", FEATURE_COLUMNS)),
        )
        head.pipeline = blob["pipeline"]
        return head


class PodiumHead(_BinaryHead):
    """Binary classifier: P(driver finishes P1-P3)."""

    def __init__(
        self,
        estimator: EstimatorKind = "logreg",
        random_state: int = 42,
        feature_columns: Sequence[str] = FEATURE_COLUMNS,
    ) -> None:
        super().__init__(
            target_max_position=3,
            estimator=estimator,
            random_state=random_state,
            feature_columns=feature_columns,
        )


class WinnerHead(_BinaryHead):
    """Binary classifier: P(driver finishes P1)."""

    def __init__(
        self,
        estimator: EstimatorKind = "logreg",
        random_state: int = 42,
        feature_columns: Sequence[str] = FEATURE_COLUMNS,
    ) -> None:
        super().__init__(
            target_max_position=1,
            estimator=estimator,
            random_state=random_state,
            feature_columns=feature_columns,
        )


# --------------------------------------------------------------------------- #
# Eval helpers
# --------------------------------------------------------------------------- #


def evaluate_head(
    head: _BinaryHead,
    feats_df: pd.DataFrame,
    actual_position: pd.Series,
    k_for_precision: int,
    season_round_key: tuple[str, str] = ("season", "round"),
) -> dict:
    """Score a trained head on a held-out frame.

    Returns AUC, Brier, precision@k (per-round avg). Per-round means:
    for each (season, round), take the top-k drivers by predicted
    probability and compute the fraction whose actual finish was within
    the target.
    """
    valid = ~actual_position.isna()
    feats = feats_df.loc[valid].reset_index(drop=True)
    actual = actual_position.loc[valid].reset_index(drop=True)
    y = (actual <= head.target_max_position).astype(int).to_numpy()
    probs = head.predict_proba(feats)

    if len(np.unique(y)) < 2:
        auc = float("nan")
    else:
        auc = float(roc_auc_score(y, probs))
    brier = float(brier_score_loss(y, probs))

    # precision@k per round
    season_col, round_col = season_round_key
    df = feats[[season_col, round_col]].copy()
    df["prob"] = probs
    df["actual"] = actual.to_numpy()
    precisions: list[float] = []
    for _, group in df.groupby([season_col, round_col]):
        top = group.nlargest(k_for_precision, "prob")
        if len(top) == 0:
            continue
        # Was the actual top-k correctly identified?
        hits = int((top["actual"] <= head.target_max_position).sum())
        precisions.append(hits / k_for_precision)
    precision_at_k = float(np.mean(precisions)) if precisions else float("nan")

    return {
        "auc": auc,
        "brier": brier,
        f"precision_at_{k_for_precision}": precision_at_k,
        "n_rows": int(len(feats)),
        "n_rounds": int(df.groupby([season_col, round_col]).ngroups),
        "positive_rate": float(y.mean()),
    }


REGISTRY_DIR = Path(__file__).resolve().parent / "registry" / "elite_heads"


__all__ = [
    "PodiumHead",
    "WinnerHead",
    "evaluate_head",
    "REGISTRY_DIR",
]
