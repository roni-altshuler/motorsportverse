"""Gradient-boosted skill regressor — an optional F1-parity signal for the blend.

The Elo stack + finishing-history signals in :mod:`.model` are each a
hand-shaped summary of one view of prior form. This module adds the view the
F1 flagship leans on: a **learned** mapping from a richer per-driver feature
vector to expected finishing position, trained on the season's own prior
rounds and ensembled across two tree learners.

Design — mirrors the FE/NASCAR ports of ``f1_prediction_utils.train_ensemble``:

* **Features** (all leakage-safe, prior-rounds-only): rolling mean/median
  finish, recent-form trend, grid-vs-finish delta (racecraft proxy), overall
  driver Elo, rookie flag, the IndyCar-specific **track-type interaction**
  (mean finish at the target round's track type minus overall — the oval /
  road-street specialist signal) and the rolling **DNF rate** (attrition drags
  mean finish and the learner should know why).
* **Target**: each driver's mean finishing position over the prior rounds.
* **Learners**: GradientBoostingRegressor + XGBRegressor, ensembled by inverse
  held-out MAE. xgboost is optional — without it the signal degrades to
  GBR-only rather than dropping ML entirely. XGB runs single-threaded
  (``n_jobs=1``; pin ``OMP_NUM_THREADS=1`` in CI) for determinism.

Era window: the learned signal trains only within the recent-regulation
window (``config.ML_FIRST_SEASON`` = 2019 onward) — earlier seasons feed the
Elo/era priors exclusively, never the regressors.

Like the other optional paths, this **degrades silently to ``None``**: flag
off, deps missing, pre-window season, or too little data all return ``None``
and let the linear blend carry the model. It never raises into the prediction
path.
"""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np

from . import config

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .datasource import IndycarDataSource

# Feature column order is fixed so the standardiser/learners see a stable matrix.
FEATURE_COLUMNS: list[str] = [
    "roll_mean_finish",     # mean finishing position over prior rounds
    "roll_median_finish",   # median finishing position (robust to one big crash)
    "form_trend",           # slope of finish over rounds (negative = improving)
    "grid_finish_delta",    # mean (grid - finish): positive = gains places
    "driver_elo",           # snapshotted overall Elo rating
    "rookie_flag",          # 1.0 if sparse prior history
    "track_type_split",     # mean finish at the target track type minus overall
    "dnf_rate",             # rolling retirement rate over prior rounds
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


def _per_driver_features(
    source: "IndycarDataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
    track_type: str,
) -> dict[str, dict[str, float]]:
    """Build the leakage-safe per-driver feature dict over ``prior_rounds`` only.

    Every quantity references prior-round classifications exclusively. Drivers
    with no prior entries get the field-mean fallback (the same neutral default
    the history signal uses), keeping rookies finite rather than NaN. Grid
    availability varies in the curated files (grid-backed old rounds carry
    none) — a missing grid contributes a neutral 0 delta, never a fabricated
    slot.
    """
    finishes: dict[str, list[float]] = {}
    type_finishes: dict[str, list[float]] = {}
    by_round: dict[str, list[tuple[int, float]]] = {}
    grid_deltas: dict[str, list[float]] = {}
    dnfs: dict[str, int] = {}
    starts: dict[str, int] = {}
    for rnd in prior_rounds:
        tt = source.track_type_for(year, rnd)
        rows = source.race_rows(year, rnd)
        if rows:
            iterator = (
                (r["code"], float(r["position"]), r.get("grid"), bool(r.get("dnf")))
                for r in rows
                if r.get("position")
            )
        else:
            iterator = (
                (res.competitor, float(res.position), res.grid, False)
                for res in source.results(year, rnd)
            )
        for code, pos, grid, dnf in iterator:
            finishes.setdefault(code, []).append(pos)
            if tt == track_type:
                type_finishes.setdefault(code, []).append(pos)
            by_round.setdefault(code, []).append((rnd, pos))
            grid_deltas.setdefault(code, []).append(float((grid or pos) - pos))
            starts[code] = starts.get(code, 0) + 1
            dnfs[code] = dnfs.get(code, 0) + int(dnf)

    rows_out: dict[str, dict[str, float]] = {}
    for code in (d["code"] for d in source.roster(year)):
        fin = finishes.get(code, [])
        n = len(fin)
        roll_mean = (sum(fin) / n) if n else field_mean
        roll_median = float(np.median(fin)) if n else field_mean
        pairs = sorted(by_round.get(code, []))
        trend = _slope([r for r, _ in pairs], [p for _, p in pairs])
        gd = grid_deltas.get(code, [])
        grid_finish_delta = (sum(gd) / len(gd)) if gd else 0.0
        tf = type_finishes.get(code, [])
        type_mean = (sum(tf) / len(tf)) if tf else roll_mean
        dnf_rate = (dnfs.get(code, 0) / starts[code]) if starts.get(code) else 0.0

        rows_out[code] = {
            "roll_mean_finish": roll_mean,
            "roll_median_finish": roll_median,
            "form_trend": trend,
            "grid_finish_delta": grid_finish_delta,
            "driver_elo": float(driver_elo.get(code, 1500.0)),
            "rookie_flag": 1.0 if n < config.ROOKIE_RACE_THRESHOLD else 0.0,
            "track_type_split": type_mean - roll_mean,
            "dnf_rate": dnf_rate,
            "_n": float(n),          # not a model feature; the gate
            "_target": roll_mean,    # learned mean finishing position (lower = faster)
        }
    return rows_out


def predict_ml_skill(
    source: "IndycarDataSource",
    year: int,
    prior_rounds: list[int],
    driver_elo: dict[str, float],
    field_mean: float,
    *,
    track_type: str = "road",
) -> dict[str, float] | None:
    """Per-driver learned mean finishing position (lower = faster), or ``None``.

    Trains a GBR + XGB ensemble on the prior-round feature matrix and predicts
    a skill score for every driver on the roster. Returns ``None`` — silently —
    when the ML path is disabled, the season predates the training window, the
    dependencies are missing, or there is too little data to learn anything.
    The caller (:func:`.model.estimate_skill`) treats ``None`` as "skip this
    signal", exactly like the other optional paths.
    """
    if (
        not config.USE_ML_SKILL
        or year < config.ML_FIRST_SEASON
        or len(prior_rounds) < config.ML_MIN_PRIOR_ROUNDS
    ):
        return None
    try:
        # scikit-learn is a hard dependency of motorsport-core, so it is
        # always present. xgboost is optional: with it we run the full
        # GBR+XGB ensemble (F1 parity); without it we degrade to GBR-only.
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler

        try:
            from xgboost import XGBRegressor

            has_xgb = True
        except Exception:
            has_xgb = False

        rows = _per_driver_features(
            source, year, prior_rounds, driver_elo, field_mean, track_type
        )
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
        if float(y_train.std()) <= 1e-9:  # degenerate target — nothing to learn
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
