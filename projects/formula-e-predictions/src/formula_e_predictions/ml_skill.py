"""Gradient-boosted skill regressor — an optional F1-parity signal for the blend.

The Elo + finishing-history + (optional) Bayesian signals in :mod:`.model` are
each a hand-shaped summary of one view of prior form. This module adds the
view the F1 flagship leans on: a **learned** mapping from a richer per-driver
feature vector to expected finishing position, trained on the season's own
prior rounds and ensembled across two tree learners.

Design — mirrors the F3 port of ``f1_prediction_utils.train_ensemble``:

* **Features** (all leakage-safe, prior-rounds-only): rolling mean/median
  finish, recent-form trend, grid-vs-finish delta (racecraft/energy-management
  proxy), teammate delta, Elo rating, rookie flag, and the FE-specific
  street-vs-circuit finish split.
* **Target**: each driver's mean finishing position over the prior rounds.
* **Learners**: GradientBoostingRegressor + XGBRegressor, ensembled by inverse
  held-out MAE. xgboost is optional — without it the signal degrades to
  GBR-only rather than dropping ML entirely.

Era window: FE's learned signal trains only within the Gen3 window
(``config.ML_FIRST_SEASON`` onward) — earlier seasons feed the Elo/era priors
exclusively, never the regressors.

Like the Bayesian path, this is **optional and degrades silently to
``None``**: flag off, deps missing, pre-Gen3 season, or too little data all
return ``None`` and let the linear blend carry the model. It never raises into
the prediction path.
"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np

from . import config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datasource import FEDataSource

# Feature column order is fixed so the standardiser/learners see a stable matrix.
FEATURE_COLUMNS: list[str] = [
    "roll_mean_finish",       # mean finishing position over prior rounds
    "roll_median_finish",     # median finishing position (robust to one bad DNF)
    "form_trend",             # slope of finish over rounds (negative = improving)
    "grid_finish_delta",      # mean (grid - finish): positive = gains places
    "teammate_delta",         # mean finish minus teammate's mean finish
    "driver_elo",             # snapshotted Elo rating
    "rookie_flag",            # 1.0 if sparse prior history
    "street_circuit_split",   # mean street finish minus mean permanent-circuit finish
]


def _slope(rounds: list[int], values: list[float]) -> float:
    """Least-squares slope of ``values`` over ``rounds`` (0.0 with < 2 points)."""
    if len(values) < 2 or len(set(rounds)) < 2:
        return 0.0
    with warnings.catch_warnings():  # short series can be poorly conditioned
        warnings.simplefilter("ignore", np.exceptions.RankWarning)
        return float(
            np.polyfit(np.asarray(rounds, dtype=float), np.asarray(values, dtype=float), 1)[0]
        )


def _venue_kind(source: "FEDataSource", year: int, rnd: int) -> str:
    try:
        kind = getattr(source.venue_for(year, rnd), "kind", "street")
        return str(getattr(kind, "value", kind) or "street")
    except Exception:
        return "street"


def _per_driver_features(
    source: "FEDataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
) -> dict[str, dict[str, float]]:
    """Build the leakage-safe per-driver feature dict over ``prior_rounds`` only.

    Every quantity references prior-round classifications exclusively. Drivers
    with no prior entries get the field-mean fallback (the same neutral default
    the history signal uses), keeping rookies finite rather than NaN.
    """
    team_of = source.team_of(year)
    by_team: dict[str, list[str]] = {}
    for code, team in team_of.items():
        by_team.setdefault(team, []).append(code)

    finishes: dict[str, list[float]] = {}
    street_finishes: dict[str, list[float]] = {}
    circuit_finishes: dict[str, list[float]] = {}
    by_round: dict[str, list[tuple[int, float]]] = {}
    grid_deltas: dict[str, list[float]] = {}
    for rnd in prior_rounds:
        kind = _venue_kind(source, year, rnd)
        bucket = street_finishes if kind == "street" else circuit_finishes
        for res in source.results(year, rnd):
            c = res.competitor
            finishes.setdefault(c, []).append(float(res.position))
            bucket.setdefault(c, []).append(float(res.position))
            by_round.setdefault(c, []).append((rnd, float(res.position)))
            grid = res.grid if res.grid else res.position
            grid_deltas.setdefault(c, []).append(float(grid - res.position))

    drv_mean = {c: (sum(v) / len(v)) if v else field_mean for c, v in finishes.items()}

    rows: dict[str, dict[str, float]] = {}
    for code in (d["code"] for d in source.roster(year)):
        fin = finishes.get(code, [])
        n = len(fin)
        roll_mean = (sum(fin) / n) if n else field_mean
        roll_median = float(np.median(fin)) if n else field_mean
        pairs = sorted(by_round.get(code, []))
        trend = _slope([r for r, _ in pairs], [p for _, p in pairs])
        gd = grid_deltas.get(code, [])
        grid_finish_delta = (sum(gd) / len(gd)) if gd else 0.0

        team = team_of.get(code, "?")
        mates = [m for m in by_team.get(team, []) if m != code]
        if mates:
            mate_mean = sum(drv_mean.get(m, field_mean) for m in mates) / len(mates)
            teammate_delta = roll_mean - mate_mean
        else:
            teammate_delta = 0.0

        sf = street_finishes.get(code, [])
        cf = circuit_finishes.get(code, [])
        street_mean = (sum(sf) / len(sf)) if sf else roll_mean
        circuit_mean = (sum(cf) / len(cf)) if cf else roll_mean
        street_circuit_split = street_mean - circuit_mean

        rows[code] = {
            "roll_mean_finish": roll_mean,
            "roll_median_finish": roll_median,
            "form_trend": trend,
            "grid_finish_delta": grid_finish_delta,
            "teammate_delta": teammate_delta,
            "driver_elo": float(driver_elo.get(code, 1500.0)),
            "rookie_flag": 1.0 if n < config.ROOKIE_RACE_THRESHOLD else 0.0,
            "street_circuit_split": street_circuit_split,
            "_n": float(n),          # not a model feature; the gate / target weight
            "_target": roll_mean,    # learned mean finishing position (lower = faster)
        }
    return rows


def predict_ml_skill(
    source: "FEDataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
) -> dict[str, float] | None:
    """Per-driver learned mean finishing position (lower = faster), or ``None``.

    Trains a GBR + XGB ensemble on the prior-round feature matrix and predicts
    a skill score for every driver on the roster. Returns ``None`` — silently —
    when the ML path is disabled, the season predates the Gen3 training window,
    the dependencies are missing, or there is too little data to learn anything.
    The caller (:func:`.model.estimate_skill`) treats ``None`` as "skip this
    signal", exactly like the optional Bayesian path.
    """
    if (
        not config.USE_ML_SKILL
        or year < config.ML_FIRST_SEASON
        or len(prior_rounds) < config.ML_MIN_PRIOR_ROUNDS
    ):
        return None
    try:
        # scikit-learn is a hard dependency of motorsport-core, so it is always
        # present. xgboost is optional: with it we run the full GBR+XGB
        # ensemble (F1 parity); without it we degrade to a GBR-only signal.
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler

        try:
            from xgboost import XGBRegressor

            has_xgb = True
        except Exception:
            has_xgb = False

        rows = _per_driver_features(source, year, prior_rounds, driver_elo, field_mean)
        codes = list(rows.keys())
        # Train only on drivers that have actually raced; predict for everyone.
        train_codes = [c for c in codes if rows[c]["_n"] > 0]
        if len(train_codes) < config.ML_MIN_TRAIN_ROWS:
            return None

        X_all = np.array([[rows[c][f] for f in FEATURE_COLUMNS] for c in codes], dtype=float)
        X_train = np.array(
            [[rows[c][f] for f in FEATURE_COLUMNS] for c in train_codes], dtype=float
        )
        y_train = np.array([rows[c]["_target"] for c in train_codes], dtype=float)
        # Degenerate target (everyone equal) — nothing to learn.
        if float(y_train.std()) <= 1e-9:
            return None

        scaler = StandardScaler().fit(X_train)
        Xs_train = scaler.transform(X_train)
        Xs_all = scaler.transform(X_all)

        # Held-out driver split for the inverse-MAE ensemble weights. Fall back
        # to in-sample scoring when the training set is too small to split.
        if len(train_codes) >= config.ML_MIN_SPLIT_ROWS:
            Xtr, Xte, ytr, yte = train_test_split(
                Xs_train, y_train, test_size=0.25, random_state=42
            )
        else:
            Xtr, Xte, ytr, yte = Xs_train, Xs_train, y_train, y_train

        gb = GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=2, random_state=42
        )
        gb.fit(Xtr, ytr)

        if not has_xgb:
            gb.fit(Xs_train, y_train)
            pred = gb.predict(Xs_all)
            return {c: float(pred[i]) for i, c in enumerate(codes)}

        xgb = XGBRegressor(
            n_estimators=250, learning_rate=0.05, max_depth=2,
            random_state=42, verbosity=0, n_jobs=1,
        )
        xgb.fit(Xtr, ytr)

        inv_gb = 1.0 / max(mean_absolute_error(yte, gb.predict(Xte)), 1e-6)
        inv_xgb = 1.0 / max(mean_absolute_error(yte, xgb.predict(Xte)), 1e-6)
        total = inv_gb + inv_xgb
        w_gb, w_xgb = inv_gb / total, inv_xgb / total

        # Refit on all training rows before the final prediction (the split fit
        # was only for weight estimation).
        gb.fit(Xs_train, y_train)
        xgb.fit(Xs_train, y_train)
        pred = w_gb * gb.predict(Xs_all) + w_xgb * xgb.predict(Xs_all)
        return {c: float(pred[i]) for i, c in enumerate(codes)}
    except Exception:  # pragma: no cover - optional path, never breaks the run
        return None
