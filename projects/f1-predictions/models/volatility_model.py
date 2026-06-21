"""Volatility model — Layer 2 of the 3-layer probabilistic race-outcome engine.

The Layer 1 ``elite_head_plus_hybrid`` ranker (see :mod:`benchmark_models`)
produces a pace-anchored ordering with elite-signal re-rank. That ordering
is correct in expectation, but races also vary in how *chaotic* they are:
high-overtake circuits, high tyre-deg races, races with elevated
safety-car probability all dilute the predictive power of a pure-pace
ordering. This module learns a scalar **volatility score V in [0, 1]**
per race so the downstream fusion layer (see
:mod:`models.probabilistic_combine`) can tilt toward the racecraft model
when V is high and toward the pace model when V is low.

Output
------
:class:`VolatilityModel.predict(features)` → ``float in [0, 1]``.
A score of 1.0 corresponds to a *very* shuffled race (mean
|actual - predicted| of ~6 positions across the field — the saturation
constant) and 0.0 to a perfectly-predicted race.

Features (all leak-safe, prior-only)
------------------------------------
* ``overtaking_difficulty`` — TrackArchetype prior (1 - this value is
  the "overtake-friendliness" signal).
* ``qualifying_importance``  — TrackArchetype prior. Higher → less
  shuffle.
* ``tire_deg_sensitivity``   — TrackArchetype prior. Higher → more
  shuffle.
* ``safety_car_probability`` — TrackArchetype prior. Higher → more
  shuffle.
* ``circuit_shuffle_prior``  — historical mean of
  |actual_position - predicted_position| at this circuit across PRIOR
  visits. NaN-handled when sparse (uses field median fallback at
  predict time).
* ``midfield_spread``        — standard deviation of
  ``predicted_lap_time`` for the CURRENT round's frame. This is
  current-round data but does NOT reveal any target (actual_position),
  so it remains leak-safe.
* ``season_shuffle_prior``   — running mean of position-shuffle across
  the season's PRIOR rounds. NaN before any prior round exists.

Skipped features (not in ``historical_predictions``)
----------------------------------------------------
* **pit stop delta impact**           — skipped: data not available
  in ``historical_predictions``; no proxy used.
* **undercut/overcut success rate**   — skipped: data not available
  in ``historical_predictions``; no proxy used.
* **restart performance**             — skipped: data not available
  in ``historical_predictions``; no proxy used.
* **tire management efficiency**      — skipped: data not available
  in ``historical_predictions``; no proxy used.
* **team pit execution strength**     — skipped: data not available
  in ``historical_predictions`` and team mapping is 2026-only;
  applying it to 2024/2025 would mis-attribute drivers.
* **weather volatility**              — skipped: data not available
  in ``historical_predictions``; ``safety_car_probability`` is a
  weak proxy for general race chaos but does not specifically encode
  weather variability.

Target
------
Per-round observed position-shuffle: mean of
|actual_position - predicted_position| across drivers, normalized to
[0, 1] by dividing by :data:`SATURATION_SHUFFLE` (default 6.0). A
shuffle of 6 positions → V ≈ 1.0.

Model
-----
``sklearn.linear_model.Ridge`` with ``StandardScaler`` and
``SimpleImputer(strategy='mean')`` so unseen NaN features are handled
gracefully. Ridge over plain OLS because we have few rounds (≤24 per
season) and many slightly-correlated features.

Leakage discipline
------------------
:func:`build_volatility_training_frame` and
:func:`build_volatility_features` BOTH pass their prior set through
:func:`leakage.assert_seasons_prior_only` at the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from leakage import assert_seasons_prior_only
from models.track_archetype import TrackArchetype


SATURATION_SHUFFLE: float = 6.0
"""Position-shuffle magnitude (in positions) at which volatility = 1.0."""


FEATURE_COLUMNS: tuple[str, ...] = (
    "overtaking_difficulty",
    "qualifying_importance",
    "tire_deg_sensitivity",
    "safety_car_probability",
    "circuit_shuffle_prior",
    "midfield_spread",
    "season_shuffle_prior",
)


REGISTRY_DIR = Path(__file__).resolve().parent / "registry" / "volatility"


def _archetype_dict(archetype: TrackArchetype | None) -> dict[str, float]:
    if archetype is None:
        return {
            "overtaking_difficulty": 0.50,
            "qualifying_importance": 0.55,
            "tire_deg_sensitivity": 0.55,
            "safety_car_probability": 0.40,
        }
    return {
        "overtaking_difficulty": float(archetype.overtaking_difficulty),
        "qualifying_importance": float(archetype.qualifying_importance),
        "tire_deg_sensitivity": float(archetype.tire_deg_sensitivity),
        "safety_car_probability": float(archetype.safety_car_probability),
    }


def _round_shuffle(df: pd.DataFrame) -> float:
    """Mean |actual - predicted| for a frame with both columns populated.

    Returns NaN if either column is empty after NaN-drop.
    """
    sub = df[["predicted_position", "actual_position"]].dropna()
    if sub.empty:
        return float("nan")
    return float((sub["predicted_position"] - sub["actual_position"]).abs().mean())


def _circuit_shuffle_prior(
    prior_rounds: pd.DataFrame, gp_key: str
) -> float:
    """Mean per-round shuffle across prior visits to ``gp_key``.

    ``prior_rounds`` is the per-round shuffle frame with columns
    ``(season, round, gp_key, shuffle)``. Returns NaN if no prior visit.
    """
    if prior_rounds.empty or not gp_key:
        return float("nan")
    sub = prior_rounds[prior_rounds["gp_key"] == gp_key]["shuffle"].dropna()
    if sub.empty:
        return float("nan")
    return float(sub.mean())


def _season_shuffle_prior(
    prior_rounds: pd.DataFrame, season: int
) -> float:
    """Mean per-round shuffle across the prior rounds in ``season``."""
    if prior_rounds.empty:
        return float("nan")
    sub = prior_rounds[prior_rounds["season"] == season]["shuffle"].dropna()
    if sub.empty:
        return float("nan")
    return float(sub.mean())


def _midfield_spread(df: pd.DataFrame) -> float:
    """Standard deviation of predicted_lap_time within a round."""
    lt = df["predicted_lap_time"].dropna()
    if len(lt) < 2:
        return float("nan")
    return float(lt.std(ddof=1))


def build_volatility_features(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
    gp_key: str,
    archetype: TrackArchetype | None,
) -> dict[str, float]:
    """Build the per-round feature vector for one (season, round).

    Parameters
    ----------
    history_df
        Frame with columns ``{season, round, driver, predicted_position,
        actual_position, predicted_lap_time}``. Rows for the target
        round must be present (we read the lap-time spread); all OTHER
        rounds are filtered to strictly-prior.
    target_season, target_round
        The round we are scoring.
    gp_key
        Circuit key for the target round (must match the gp_key
        rendered for prior rounds via the same mapping used by the
        caller; the caller is responsible for this).
    archetype
        TrackArchetype for the target circuit (may be None).

    Returns
    -------
    dict mapping each entry in :data:`FEATURE_COLUMNS` to a float
    (NaN allowed for sparse-prior features; the model imputes at
    predict time).
    """
    required = {
        "season", "round", "driver",
        "predicted_position", "actual_position", "predicted_lap_time",
        "gp_key",
    }
    missing = required - set(history_df.columns)
    if missing:
        raise ValueError(
            f"history_df missing required columns: {sorted(missing)}"
        )

    prior_full = history_df[
        ~(
            (history_df["season"] > target_season)
            | (
                (history_df["season"] == target_season)
                & (history_df["round"] >= target_round)
            )
        )
    ].copy()
    assert_seasons_prior_only(
        prior_full[["season", "round"]].to_dict("records"),
        current_season=target_season,
        current_round=target_round,
        label=f"volatility_features prior for ({target_season},{target_round})",
    )

    # Compute per-round shuffle for prior rounds.
    prior_rounds: list[dict] = []
    for (s, r), grp in prior_full.groupby(["season", "round"], sort=True):
        prior_rounds.append(
            {
                "season": int(s),
                "round": int(r),
                "gp_key": str(grp["gp_key"].iloc[0]) if not grp.empty else "",
                "shuffle": _round_shuffle(grp),
            }
        )
    prior_round_df = pd.DataFrame(
        prior_rounds, columns=["season", "round", "gp_key", "shuffle"]
    )

    # Current-round frame (for midfield spread — leak-safe because we use
    # predicted_lap_time only, never actual).
    target_df = history_df[
        (history_df["season"] == target_season)
        & (history_df["round"] == target_round)
    ]

    archetype_feats = _archetype_dict(archetype)
    return {
        "overtaking_difficulty": archetype_feats["overtaking_difficulty"],
        "qualifying_importance": archetype_feats["qualifying_importance"],
        "tire_deg_sensitivity": archetype_feats["tire_deg_sensitivity"],
        "safety_car_probability": archetype_feats["safety_car_probability"],
        "circuit_shuffle_prior": _circuit_shuffle_prior(prior_round_df, gp_key),
        "midfield_spread": _midfield_spread(target_df),
        "season_shuffle_prior": _season_shuffle_prior(prior_round_df, target_season),
    }


def build_volatility_training_frame(
    history_df: pd.DataFrame,
    target_rounds: Sequence[tuple[int, int, str, TrackArchetype | None]],
) -> tuple[pd.DataFrame, np.ndarray]:
    """Assemble (X, y) for training the volatility regressor.

    For each (season, round, gp_key, archetype) tuple, build the
    feature vector via :func:`build_volatility_features` (leak-safe)
    and the target (observed shuffle, normalized).

    Skips rounds with no actual_position rows (i.e. nothing to score).
    """
    rows: list[dict] = []
    targets: list[float] = []
    for (season, round_, gp_key, arche) in target_rounds:
        feats = build_volatility_features(
            history_df, season, round_, gp_key, arche
        )
        target_df = history_df[
            (history_df["season"] == season) & (history_df["round"] == round_)
        ]
        shuffle = _round_shuffle(target_df)
        if not np.isfinite(shuffle):
            continue
        v = float(np.clip(shuffle / SATURATION_SHUFFLE, 0.0, 1.0))
        feats_row = {**feats, "season": season, "round": round_}
        rows.append(feats_row)
        targets.append(v)
    return pd.DataFrame(rows), np.array(targets, dtype=float)


@dataclass
class VolatilityModel:
    """Ridge regressor on the per-round volatility features."""

    alpha: float = 1.0
    random_state: int = 42
    feature_columns: Sequence[str] = field(default=FEATURE_COLUMNS)
    pipeline: Pipeline | None = None

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "VolatilityModel":
        if len(X) == 0:
            raise ValueError("cannot fit VolatilityModel on empty frame")
        Xm = X[list(self.feature_columns)].to_numpy(dtype=float)
        ym = np.asarray(y, dtype=float)
        self.pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="mean")),
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=self.alpha, random_state=self.random_state)),
            ]
        )
        self.pipeline.fit(Xm, ym)
        return self

    def predict(self, X: pd.DataFrame | dict[str, float]) -> np.ndarray:
        """Predict volatility V in [0,1] for one or many rounds.

        ``X`` may be a DataFrame (multi-row) or a single feature dict.
        Output is always a 1-D numpy array.
        """
        if self.pipeline is None:
            raise RuntimeError("call fit() before predict()")
        if isinstance(X, dict):
            X = pd.DataFrame([X])
        Xm = X[list(self.feature_columns)].to_numpy(dtype=float)
        raw = self.pipeline.predict(Xm)
        return np.clip(raw, 0.0, 1.0)

    def predict_one(self, features: dict[str, float]) -> float:
        return float(self.predict(features)[0])

    def coefficients(self) -> dict[str, float]:
        """Return standardized Ridge coefficients per feature."""
        if self.pipeline is None:
            raise RuntimeError("call fit() before coefficients()")
        ridge: Ridge = self.pipeline.named_steps["ridge"]
        return {
            name: float(c)
            for name, c in zip(self.feature_columns, ridge.coef_)
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "alpha": self.alpha,
                "random_state": self.random_state,
                "feature_columns": list(self.feature_columns),
                "saturation_shuffle": SATURATION_SHUFFLE,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "VolatilityModel":
        blob = joblib.load(path)
        model = cls(
            alpha=float(blob.get("alpha", 1.0)),
            random_state=int(blob.get("random_state", 42)),
            feature_columns=tuple(blob.get("feature_columns", FEATURE_COLUMNS)),
        )
        model.pipeline = blob["pipeline"]
        return model


__all__ = [
    "SATURATION_SHUFFLE",
    "FEATURE_COLUMNS",
    "REGISTRY_DIR",
    "VolatilityModel",
    "build_volatility_features",
    "build_volatility_training_frame",
]
