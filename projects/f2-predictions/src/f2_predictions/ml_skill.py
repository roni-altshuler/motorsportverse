"""Gradient-boosted skill regressor — an optional F1-parity signal for the blend.

The Elo + finishing-history + (optional) Bayesian signals in :mod:`.model` are
each a *hand-shaped* summary of one view of prior form. This module adds the
view the F1 flagship leans on: a **learned** mapping from a richer per-driver
feature vector to expected finishing position, trained on the season's own prior
rounds and ensembled across two tree learners.

Design — mirrors ``f1_prediction_utils.train_ensemble``:

* **Features** (all leakage-safe, prior-rounds-only): rolling mean/median finish,
  recent-form trend (slope of finish over rounds), grid-vs-finish delta
  (overtaking/racecraft proxy), teammate delta, Elo rating, rookie flag, and the
  F2-specific sprint-vs-feature finish split.
* **Target**: each driver's mean finishing position over the prior rounds — the
  same "lower = better" orientation the rest of the model uses, learned rather
  than averaged so the model can exploit feature interactions (e.g. a rookie with
  a strong grid-vs-finish delta is improving faster than the flat mean implies).
* **Learners**: :class:`~sklearn.ensemble.GradientBoostingRegressor` +
  :class:`~xgboost.XGBRegressor`, ensembled by **inverse held-out MAE** exactly
  like the F1 ensemble. Features are standardised (``StandardScaler``) so no
  single column dominates the trees' early splits.

Like the Bayesian path in :func:`.model._bayesian_skill`, this is **optional and
degrades silently to ``None``**: flag off, scikit-learn/xgboost missing, or too
little data (fewer than :data:`config.ML_MIN_TRAIN_ROWS` driver-rows, or a single
prior round so every feature is flat) all return ``None`` and let the linear blend
carry the model. It never raises into the prediction path.

The returned value is a per-driver *predicted mean finishing position* (lower =
faster). :func:`.model.estimate_skill` z-scores and orients it consistently with
the other signals before folding it into the pace blend.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from . import config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datasource import F2DataSource

SPRINT = "sprint"
FEATURE = "feature"

# Feature column order is fixed so the standardiser/learners see a stable matrix.
FEATURE_COLUMNS: list[str] = [
    "roll_mean_finish",     # mean finishing position over prior rounds
    "roll_median_finish",   # median finishing position (robust to one bad DNF)
    "form_trend",           # slope of finish over rounds (negative = improving)
    "grid_finish_delta",    # mean (grid - finish): positive = gains places
    "teammate_delta",       # mean finish minus teammate's mean finish
    "driver_elo",           # snapshotted Elo rating
    "rookie_flag",          # 1.0 if sparse prior history
    "sprint_feature_split",  # mean sprint finish minus mean feature finish
]


def _slope(rounds: list[int], values: list[float]) -> float:
    """Least-squares slope of ``values`` over ``rounds`` (0.0 with < 2 points)."""
    if len(values) < 2:
        return 0.0
    return float(np.polyfit(np.asarray(rounds, dtype=float), np.asarray(values, dtype=float), 1)[0])


def _per_driver_features(
    source: "F2DataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
) -> dict[str, dict[str, float]]:
    """Build the leakage-safe per-driver feature dict over ``prior_rounds`` only.

    Every quantity references prior-round classifications exclusively, so the
    matrix is safe to train on for a forecast of ``current_round``. Drivers with
    no prior entries get the field-mean fallback (the same neutral default the
    history signal uses), keeping rookies finite rather than NaN.
    """
    teammate_of = config.TEAM_OF
    by_team: dict[str, list[str]] = {}
    for code, team in teammate_of.items():
        by_team.setdefault(team, []).append(code)

    # Collect, per driver, the chronological (round, finish) pairs split by race type.
    finishes: dict[str, list[float]] = {}
    sprint_finishes: dict[str, list[float]] = {}
    feature_finishes: dict[str, list[float]] = {}
    by_round: dict[str, list[tuple[int, float]]] = {}
    grid_deltas: dict[str, list[float]] = {}
    for rnd in prior_rounds:
        races = source.race_results_for_round(year, rnd)
        for race_type, bucket in ((SPRINT, sprint_finishes), (FEATURE, feature_finishes)):
            for res in races[race_type]:
                c = res.competitor
                finishes.setdefault(c, []).append(float(res.position))
                bucket.setdefault(c, []).append(float(res.position))
                by_round.setdefault(c, []).append((rnd, float(res.position)))
                grid = res.grid if res.grid else res.position
                grid_deltas.setdefault(c, []).append(float(grid - res.position))

    # Per-driver team-mean finish (for the teammate delta) computed prior-only.
    drv_mean = {c: (sum(v) / len(v)) if v else field_mean for c, v in finishes.items()}

    rows: dict[str, dict[str, float]] = {}
    for code in (d["code"] for d in config.DRIVERS):
        fin = finishes.get(code, [])
        n = len(fin)
        roll_mean = (sum(fin) / n) if n else field_mean
        roll_median = float(np.median(fin)) if n else field_mean
        pairs = sorted(by_round.get(code, []))
        trend = _slope([r for r, _ in pairs], [p for _, p in pairs])
        gd = grid_deltas.get(code, [])
        grid_finish_delta = (sum(gd) / len(gd)) if gd else 0.0

        team = teammate_of.get(code, "?")
        mates = [m for m in by_team.get(team, []) if m != code]
        if mates:
            mate_mean = sum(drv_mean.get(m, field_mean) for m in mates) / len(mates)
            teammate_delta = roll_mean - mate_mean
        else:
            teammate_delta = 0.0

        sf = sprint_finishes.get(code, [])
        ff = feature_finishes.get(code, [])
        sprint_mean = (sum(sf) / len(sf)) if sf else roll_mean
        feature_mean = (sum(ff) / len(ff)) if ff else roll_mean
        sprint_feature_split = sprint_mean - feature_mean

        rows[code] = {
            "roll_mean_finish": roll_mean,
            "roll_median_finish": roll_median,
            "form_trend": trend,
            "grid_finish_delta": grid_finish_delta,
            "teammate_delta": teammate_delta,
            "driver_elo": float(driver_elo.get(code, 1500.0)),
            "rookie_flag": 1.0 if n < config.ROOKIE_RACE_THRESHOLD else 0.0,
            "sprint_feature_split": sprint_feature_split,
            "_n": float(n),          # not a model feature; used only as the gate / target weight
            "_target": roll_mean,    # learned mean finishing position (lower = faster)
        }
    return rows


def predict_ml_skill(
    source: "F2DataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
) -> dict[str, float] | None:
    """Per-driver learned mean finishing position (lower = faster), or ``None``.

    Trains a GBR + XGB ensemble on the prior-round feature matrix and predicts a
    skill score for every driver on the roster. Returns ``None`` — silently — when
    the ML path is disabled, the dependencies are missing, or there is too little
    data to learn anything (single prior round, or a feature matrix with no
    variance). The caller (:func:`.model.estimate_skill`) treats ``None`` as
    "skip this signal", exactly like the optional Bayesian path.

    The ensemble weighting mirrors the F1 flagship: each learner is scored by MAE
    on a held-out driver split and combined by inverse-MAE weights, so the more
    reliable learner on this round's data carries more of the blend.
    """
    if not config.USE_ML_SKILL or len(prior_rounds) < config.ML_MIN_PRIOR_ROUNDS:
        return None
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBRegressor

        rows = _per_driver_features(source, year, prior_rounds, driver_elo, field_mean)
        codes = list(rows.keys())
        # Train only on drivers that have actually raced; predict for everyone.
        train_codes = [c for c in codes if rows[c]["_n"] > 0]
        if len(train_codes) < config.ML_MIN_TRAIN_ROWS:
            return None

        X_all = np.array([[rows[c][f] for f in FEATURE_COLUMNS] for c in codes], dtype=float)
        X_train = np.array([[rows[c][f] for f in FEATURE_COLUMNS] for c in train_codes], dtype=float)
        y_train = np.array([rows[c]["_target"] for c in train_codes], dtype=float)
        # Degenerate target (everyone equal) — nothing to learn, let the blend run.
        if float(y_train.std()) <= 1e-9:
            return None

        scaler = StandardScaler().fit(X_train)
        Xs_train = scaler.transform(X_train)
        Xs_all = scaler.transform(X_all)

        # Held-out driver split for the inverse-MAE ensemble weights. Fall back to
        # in-sample scoring when the training set is too small to split safely.
        if len(train_codes) >= config.ML_MIN_SPLIT_ROWS:
            Xtr, Xte, ytr, yte = train_test_split(Xs_train, y_train, test_size=0.25, random_state=42)
        else:
            Xtr, Xte, ytr, yte = Xs_train, Xs_train, y_train, y_train

        gb = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=2, random_state=42)
        xgb = XGBRegressor(n_estimators=250, learning_rate=0.05, max_depth=2, random_state=42, verbosity=0)
        gb.fit(Xtr, ytr)
        xgb.fit(Xtr, ytr)

        inv_gb = 1.0 / max(mean_absolute_error(yte, gb.predict(Xte)), 1e-6)
        inv_xgb = 1.0 / max(mean_absolute_error(yte, xgb.predict(Xte)), 1e-6)
        total = inv_gb + inv_xgb
        w_gb, w_xgb = inv_gb / total, inv_xgb / total

        # Refit on all training rows before the final prediction (the split fit was
        # only for weight estimation — mirrors train_ensemble predicting on X_all).
        gb.fit(Xs_train, y_train)
        xgb.fit(Xs_train, y_train)
        pred = w_gb * gb.predict(Xs_all) + w_xgb * xgb.predict(Xs_all)
        return {c: float(pred[i]) for i, c in enumerate(codes)}
    except Exception:  # pragma: no cover - optional path, never breaks the run
        return None
