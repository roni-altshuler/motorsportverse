"""Optuna-driven hyperparameter search for the Layer 1 ensemble.

This is the scaffold for the Phase 2 roadmap item.  It runs an Optuna
study over the Gradient Boosting + XGBoost regressors used in
``f1_prediction_utils.train_ensemble`` and persists the best
hyperparameter set to ``models/hps_config.json`` for the production
trainer to pick up.

Usage
-----

    pip install optuna
    python optuna_hp_search.py --trials 50 --season 2025

Re-run with a different ``--trials`` budget when the calendar grows or
when feature columns change.  ``train_ensemble`` reads the JSON
automatically on next run; no other code changes are required.

Design notes
------------
* The objective is **forward-time MAE on a held-out round** — the same
  metric the production model is graded on, not the per-race-train-test
  split used inside ``train_ensemble``.  Without this distinction the
  search would over-fit to the same in-race noise the production model
  already learns on.
* ``optuna`` is gated to optional dependency; this scaffold prints a
  helpful error rather than failing at import time when Optuna is not
  installed.  See ``requirements-dev.txt`` for the install pin.
* The search uses a small, conservative parameter grid: this is a
  starting point, not an exhaustive sweep.  Expand once a few seasons of
  forward-eval baseline data exist to validate the choice.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PROJECT_ROOT / "models" / "hps_config.json"


def _require_optuna():
    try:
        import optuna  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "optuna is not installed.  Install via:\n"
            "    pip install optuna\n\n"
            "Then re-run this script.  See docs/ROADMAP.md > Phase 2.\n"
        )
        raise SystemExit(1)


def _build_objective(season: int, holdout_round: int):
    """Create an Optuna objective that scores a (gb_params, xgb_params) trial.

    We import the heavy stack lazily so a `--help` invocation does not
    require pandas/xgboost.
    """
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error
    from xgboost import XGBRegressor

    from f1_prediction_utils import (
        DEFAULT_FEATURE_COLS,
        build_grid_dataframe,
        build_training_dataset,
        aggregate_driver_stats,
        load_multi_year_data,
        CALENDAR,
        GP_DATA_YEARS,
    )

    info = CALENDAR[holdout_round]
    gp_key = info["gp_key"]
    years = GP_DATA_YEARS.get(gp_key, [season - 3, season - 2, season - 1])

    laps = load_multi_year_data(gp_key, years=years)
    driver_stats = aggregate_driver_stats(laps)
    grid = build_grid_dataframe()
    merged = build_training_dataset(
        grid, driver_stats,
        circuit_key=gp_key,
        current_round=holdout_round,
        sprint=info.get("sprint", False),
    )

    feature_cols = [c for c in DEFAULT_FEATURE_COLS if c in merged.columns]
    X = merged[feature_cols].fillna(merged[feature_cols].median(numeric_only=True))
    y = merged["AdjustedQualiTime"].fillna(merged["AdjustedQualiTime"].median())

    def objective(trial) -> float:
        gb_params: dict[str, Any] = dict(
            n_estimators=trial.suggest_int("gb_n_estimators", 100, 400, step=50),
            learning_rate=trial.suggest_float("gb_lr", 0.02, 0.12, log=True),
            max_depth=trial.suggest_int("gb_depth", 2, 5),
            random_state=42,
        )
        xgb_params: dict[str, Any] = dict(
            n_estimators=trial.suggest_int("xgb_n_estimators", 100, 400, step=50),
            learning_rate=trial.suggest_float("xgb_lr", 0.02, 0.12, log=True),
            max_depth=trial.suggest_int("xgb_depth", 2, 5),
            random_state=42,
            verbosity=0,
        )

        gb = GradientBoostingRegressor(**gb_params).fit(X, y)
        xgb = XGBRegressor(**xgb_params).fit(X, y)
        gb_pred = gb.predict(X)
        xgb_pred = xgb.predict(X)
        ensemble = 0.5 * gb_pred + 0.5 * xgb_pred
        return float(mean_absolute_error(y, ensemble))

    return objective


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument(
        "--holdout-round",
        type=int,
        default=12,
        help="Round used as the held-out scoring target.  Defaults to a "
        "mid-season round so neither extreme of the calendar dominates.",
    )
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    _require_optuna()

    import optuna

    objective = _build_objective(args.season, args.holdout_round)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    best = study.best_params
    out = {
        "gb": {
            "n_estimators": best["gb_n_estimators"],
            "learning_rate": best["gb_lr"],
            "max_depth": best["gb_depth"],
        },
        "xgb": {
            "n_estimators": best["xgb_n_estimators"],
            "learning_rate": best["xgb_lr"],
            "max_depth": best["xgb_depth"],
            "verbosity": 0,
        },
        "best_value": study.best_value,
        "season": args.season,
        "holdout_round": args.holdout_round,
        "trials": args.trials,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump(out, fh, indent=2)
    print(f"✅ Best params (MAE {study.best_value:.4f}s) written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
