"""LightGBM / CatBoost vs the production XGBoost ensemble.

Phase 2 roadmap item.  XGBoost is currently the workhorse in
``f1_prediction_utils.train_ensemble``; LightGBM and CatBoost typically
match-or-beat XGBoost on tabular regression and ship with calibration
benefits (CatBoost) and faster training (LightGBM).

This script runs a like-for-like benchmark on a single round's
training frame: same features, same target, same train/test split.
Reports MAE on the held-out subset for each library so we can decide
whether to swap in a Phase 2 follow-up.

LightGBM and CatBoost are optional dependencies — the script reports
a friendly skip message when either is missing.

Usage::

    pip install lightgbm catboost
    python benchmark_gbm_libraries.py --round 5 --season 2026
"""
from __future__ import annotations

import argparse
from typing import Optional


def _import_lightgbm():
    try:
        from lightgbm import LGBMRegressor

        return LGBMRegressor
    except ImportError:
        return None


def _import_catboost():
    try:
        from catboost import CatBoostRegressor

        return CatBoostRegressor
    except ImportError:
        return None


def benchmark_round(round_num: int, season: int) -> int:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split
    from xgboost import XGBRegressor

    # Lazy imports — keep --help fast.
    from f1_prediction_utils import (
        DEFAULT_FEATURE_COLS,
        CALENDAR,
        GP_DATA_YEARS,
        aggregate_driver_stats,
        build_grid_dataframe,
        build_training_dataset,
        load_multi_year_data,
    )

    info = CALENDAR[round_num]
    gp_key = info["gp_key"]
    years = GP_DATA_YEARS.get(gp_key, [season - 3, season - 2, season - 1])

    laps = load_multi_year_data(gp_key, years=years)
    driver_stats = aggregate_driver_stats(laps)
    grid = build_grid_dataframe()
    merged = build_training_dataset(
        grid, driver_stats,
        circuit_key=gp_key,
        current_round=round_num,
        sprint=info.get("sprint", False),
    )

    feature_cols = [c for c in DEFAULT_FEATURE_COLS if c in merged.columns]
    X = merged[feature_cols].fillna(merged[feature_cols].median(numeric_only=True))
    y = merged["AdjustedQualiTime"].fillna(merged["AdjustedQualiTime"].median()).values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42,
    )

    results: list[tuple[str, Optional[float]]] = []

    # GradientBoosting (sklearn baseline)
    gb = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=3, random_state=42,
    ).fit(X_train, y_train)
    results.append(("Gradient Boosting", float(mean_absolute_error(y_test, gb.predict(X_test)))))

    # XGBoost (production)
    xgb = XGBRegressor(
        n_estimators=250, learning_rate=0.05, max_depth=3,
        random_state=42, verbosity=0,
    ).fit(X_train, y_train)
    results.append(("XGBoost", float(mean_absolute_error(y_test, xgb.predict(X_test)))))

    # LightGBM (optional)
    LGBM = _import_lightgbm()
    if LGBM is not None:
        lgbm = LGBM(
            n_estimators=250, learning_rate=0.05, max_depth=3,
            random_state=42, verbose=-1,
        ).fit(X_train, y_train)
        results.append(("LightGBM", float(mean_absolute_error(y_test, lgbm.predict(X_test)))))
    else:
        results.append(("LightGBM", None))

    # CatBoost (optional)
    CatBoost = _import_catboost()
    if CatBoost is not None:
        cat = CatBoost(
            iterations=250, learning_rate=0.05, depth=4,
            random_seed=42, verbose=False,
        ).fit(X_train, y_train)
        results.append(("CatBoost", float(mean_absolute_error(y_test, cat.predict(X_test)))))
    else:
        results.append(("CatBoost", None))

    print()
    print(f"Benchmark — Round {round_num} ({gp_key}), {len(X_test)} held-out rows")
    print("─" * 50)
    for name, mae in results:
        if mae is None:
            print(f"{name:<20} (skipped — not installed)")
        else:
            print(f"{name:<20} MAE = {mae:.4f}s")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args(argv)
    return benchmark_round(args.round, args.season)


if __name__ == "__main__":
    raise SystemExit(main())
