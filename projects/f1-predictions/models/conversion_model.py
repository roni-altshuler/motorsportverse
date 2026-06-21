"""Conversion model — Layer 3 of the 3-layer probabilistic engine.

Where the elite-head re-ranker (Layer 1) measures *pace-elite signal*,
this layer measures **conversion** — given a driver was projected to
start near the front, how often do they actually land on the podium /
win? Race-day chaos, racecraft, pit-stop execution, and luck all live
inside this conditional. We can't measure those directly from
``historical_predictions`` (the DB has no telemetry, no pit data, no
grid column), but we CAN measure their aggregate effect through the
historical conversion ratios on top of the *predicted* finishing
position.

Heads
-----
* :class:`ConversionWinHead`     — P(driver finishes P1)    | features
* :class:`ConversionPodiumHead`  — P(driver finishes P1-P3) | features

Both are ``sklearn.linear_model.LogisticRegression`` with
``class_weight='balanced'`` — same pattern as ``elite_heads`` so the
calibration story matches.

Features (all leak-safe, prior-only)
------------------------------------
* ``predicted_position``                — Layer 1's predicted_position.
  Used as a stand-in for **grid position**; the DB does not store a
  grid column so this is the closest proxy. Documented in the public
  module docstring AND inside the markdown report.
* ``predicted_lap_time_gap_to_leader``  — driver's
  predicted_lap_time minus the fastest predicted_lap_time in the
  current-round frame. Current-round data but reveals nothing about
  actual finishing position, so leak-safe.
* ``driver_podium_given_top3``          — historical fraction of prior
  races where driver was predicted top-3 AND finished on the podium,
  divided by the count of prior races where they were predicted top-3.
  NaN if the driver was never predicted top-3 in priors.
* ``driver_win_given_p1``               — historical fraction of prior
  races where driver was predicted P1 AND won, divided by the count of
  prior races where they were predicted P1. NaN if never predicted P1.
* ``driver_racecraft``                  — mean of
  ``predicted_position - actual_position`` across all prior races
  with a settled finish (positive = gains positions on race day;
  negative = loses positions). NaN if no prior races.
* ``driver_circuit_conversion``         — same as
  ``driver_podium_given_top3`` but restricted to prior visits at this
  circuit. NaN sentinel when no prior visits.

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
  in ``historical_predictions``; no proxy used.

Training discipline
-------------------
:func:`build_conversion_features` mirrors the elite-heads training
discipline: rebuild features on a strictly-prior history frame for
each target round, train two LogReg classifiers, predict on the
target round, repeat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from leakage import assert_seasons_prior_only


FEATURE_COLUMNS: tuple[str, ...] = (
    "predicted_position",
    "predicted_lap_time_gap_to_leader",
    "driver_podium_given_top3",
    "driver_win_given_p1",
    "driver_racecraft",
    "driver_circuit_conversion",
)


REGISTRY_DIR = Path(__file__).resolve().parent / "registry" / "conversion"


HeadKind = Literal["podium", "win"]


def _safe_ratio(num: int, den: int, min_den: int = 1) -> float:
    if den < min_den:
        return float("nan")
    return float(num) / float(den)


def _driver_podium_given_top3(driver_hist: pd.DataFrame, min_count: int = 2) -> float:
    """Among prior races where this driver was predicted top-3,
    fraction where they actually finished on the podium."""
    if driver_hist.empty:
        return float("nan")
    mask = driver_hist["predicted_position"] <= 3
    sub = driver_hist[mask]
    if len(sub) < min_count:
        return float("nan")
    podium_hits = int((sub["actual_position"] <= 3).sum())
    return _safe_ratio(podium_hits, len(sub), min_den=min_count)


def _driver_win_given_p1(driver_hist: pd.DataFrame, min_count: int = 1) -> float:
    """Among prior races where driver was predicted P1, fraction where they won."""
    if driver_hist.empty:
        return float("nan")
    mask = driver_hist["predicted_position"] == 1
    sub = driver_hist[mask]
    if len(sub) < min_count:
        return float("nan")
    wins = int((sub["actual_position"] == 1).sum())
    return _safe_ratio(wins, len(sub), min_den=min_count)


def _driver_racecraft(driver_hist: pd.DataFrame) -> float:
    """Mean (predicted_position - actual_position) across prior races."""
    if driver_hist.empty:
        return float("nan")
    sub = driver_hist[["predicted_position", "actual_position"]].dropna()
    if sub.empty:
        return float("nan")
    return float((sub["predicted_position"] - sub["actual_position"]).mean())


def _driver_circuit_conversion(
    driver_hist: pd.DataFrame, gp_key: str, min_count: int = 1
) -> float:
    """Fraction of prior visits to gp_key where driver finished on podium
    GIVEN they were predicted top-6 (so we measure conversion at this
    circuit, not just any podium)."""
    if driver_hist.empty or not gp_key:
        return float("nan")
    sub = driver_hist[driver_hist["gp_key"] == gp_key]
    if sub.empty:
        return float("nan")
    sub = sub[sub["predicted_position"] <= 6]
    if len(sub) < min_count:
        return float("nan")
    podium_hits = int((sub["actual_position"] <= 3).sum())
    return _safe_ratio(podium_hits, len(sub), min_den=min_count)


def build_conversion_features(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
    gp_key: str,
) -> pd.DataFrame:
    """Build per-driver conversion features for one round.

    Parameters
    ----------
    history_df
        Frame with columns ``{season, round, driver, predicted_position,
        actual_position, predicted_lap_time, gp_key}``.
    target_season, target_round
        The round we're scoring.
    gp_key
        Circuit key for the target round (used by the driver-circuit
        conversion feature).

    Returns
    -------
    pd.DataFrame
        One row per driver in the target round, columns ``driver``,
        ``season``, ``round``, plus :data:`FEATURE_COLUMNS`.
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

    prior = history_df[
        ~(
            (history_df["season"] > target_season)
            | (
                (history_df["season"] == target_season)
                & (history_df["round"] >= target_round)
            )
        )
    ].copy()
    # Conversion features need a settled actual_position to be useful.
    prior = prior[prior["actual_position"].notna()].copy()
    assert_seasons_prior_only(
        prior[["season", "round"]].to_dict("records"),
        current_season=target_season,
        current_round=target_round,
        label=f"conversion_features prior for ({target_season},{target_round})",
    )

    target = history_df[
        (history_df["season"] == target_season)
        & (history_df["round"] == target_round)
    ].copy()
    if target.empty:
        return pd.DataFrame(
            columns=("driver", "season", "round", *FEATURE_COLUMNS)
        )

    target = target.sort_values("predicted_position").reset_index(drop=True)
    pole_lap = float(target["predicted_lap_time"].min()) if not target["predicted_lap_time"].isna().all() else float("nan")

    rows: list[dict] = []
    for _, r in target.iterrows():
        driver = str(r["driver"])
        driver_hist = prior[prior["driver"] == driver]
        row_pred = float(r["predicted_position"]) if pd.notna(r["predicted_position"]) else float("nan")
        row_lap = float(r["predicted_lap_time"]) if pd.notna(r["predicted_lap_time"]) else float("nan")
        gap = (row_lap - pole_lap) if (np.isfinite(row_lap) and np.isfinite(pole_lap)) else float("nan")
        rows.append(
            {
                "driver": driver,
                "season": target_season,
                "round": target_round,
                "predicted_position": row_pred,
                "predicted_lap_time_gap_to_leader": gap,
                "driver_podium_given_top3": _driver_podium_given_top3(driver_hist),
                "driver_win_given_p1": _driver_win_given_p1(driver_hist),
                "driver_racecraft": _driver_racecraft(driver_hist),
                "driver_circuit_conversion": _driver_circuit_conversion(
                    driver_hist, gp_key
                ),
            }
        )
    return pd.DataFrame(rows)


def build_conversion_features_batch(
    history_df: pd.DataFrame,
    target_rounds: Iterable[tuple[int, int, str]],
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for season, round_, gp_key in target_rounds:
        feats = build_conversion_features(history_df, season, round_, gp_key)
        if not feats.empty:
            parts.append(feats)
    if not parts:
        return pd.DataFrame(
            columns=("driver", "season", "round", *FEATURE_COLUMNS)
        )
    return pd.concat(parts, ignore_index=True)


def _make_pipeline(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    solver="lbfgs",
                    random_state=random_state,
                ),
            ),
        ]
    )


@dataclass
class _ConversionHead:
    target_max_position: int
    random_state: int = 42
    feature_columns: Sequence[str] = field(default=FEATURE_COLUMNS)
    pipeline: Pipeline | None = None

    def _y_from_actual(self, actual_position: pd.Series) -> np.ndarray:
        return (actual_position <= self.target_max_position).astype(int).to_numpy()

    def fit(self, feats: pd.DataFrame, actual_position: pd.Series) -> "_ConversionHead":
        # Drop rows with missing actuals.
        if actual_position.isna().any():
            mask = ~actual_position.isna()
            feats = feats.loc[mask].reset_index(drop=True)
            actual_position = actual_position.loc[mask].reset_index(drop=True)
        X = feats[list(self.feature_columns)].to_numpy(dtype=float)
        y = self._y_from_actual(actual_position)
        if len(np.unique(y)) < 2:
            raise ValueError(
                f"only one class present in y for target<=P{self.target_max_position};"
                " cannot train conversion head"
            )
        self.pipeline = _make_pipeline(self.random_state)
        self.pipeline.fit(X, y)
        return self

    def predict_proba(self, feats: pd.DataFrame) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("call fit() before predict_proba()")
        X = feats[list(self.feature_columns)].to_numpy(dtype=float)
        probs = self.pipeline.predict_proba(X)
        clf = self.pipeline.named_steps["clf"]
        classes = list(clf.classes_)
        pos_idx = classes.index(1) if 1 in classes else len(classes) - 1
        return probs[:, pos_idx]

    def coefficients(self) -> dict[str, float]:
        """Standardized LogReg coefficients per feature (raw, signed)."""
        if self.pipeline is None:
            raise RuntimeError("call fit() before coefficients()")
        clf: LogisticRegression = self.pipeline.named_steps["clf"]
        return {
            name: float(c)
            for name, c in zip(self.feature_columns, clf.coef_[0])
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "target_max_position": self.target_max_position,
                "random_state": self.random_state,
                "feature_columns": list(self.feature_columns),
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "_ConversionHead":
        blob = joblib.load(path)
        head = cls.__new__(cls)
        _ConversionHead.__init__(
            head,
            target_max_position=int(blob["target_max_position"]),
            random_state=int(blob.get("random_state", 42)),
            feature_columns=tuple(blob.get("feature_columns", FEATURE_COLUMNS)),
        )
        head.pipeline = blob["pipeline"]
        return head


class ConversionPodiumHead(_ConversionHead):
    """Conversion-features classifier for P(driver finishes P1-P3)."""

    def __init__(
        self,
        random_state: int = 42,
        feature_columns: Sequence[str] = FEATURE_COLUMNS,
    ) -> None:
        super().__init__(
            target_max_position=3,
            random_state=random_state,
            feature_columns=feature_columns,
        )


class ConversionWinHead(_ConversionHead):
    """Conversion-features classifier for P(driver finishes P1)."""

    def __init__(
        self,
        random_state: int = 42,
        feature_columns: Sequence[str] = FEATURE_COLUMNS,
    ) -> None:
        super().__init__(
            target_max_position=1,
            random_state=random_state,
            feature_columns=feature_columns,
        )


__all__ = [
    "FEATURE_COLUMNS",
    "REGISTRY_DIR",
    "ConversionPodiumHead",
    "ConversionWinHead",
    "build_conversion_features",
    "build_conversion_features_batch",
]
