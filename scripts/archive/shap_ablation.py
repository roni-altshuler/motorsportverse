"""SHAP-based per-driver prediction-error decomposition.

Phase 3 roadmap item.  When the model badly misses a driver's
finishing position, we want to know *which features* drove the
prediction.  SHAP values give us a per-feature contribution to each
prediction; aggregating those by driver and feature surfaces the
"biggest movers" for each round.

The output JSON is consumed by a future `/accuracy/ablation` page.
For now this script produces the data file; UI wiring is a follow-up.

SHAP is an optional dependency — the script prints a friendly skip
message when it isn't installed.

Usage::

    pip install shap
    python shap_ablation.py --round 5 --season 2026 \
        --output website/public/data/ablation/round_05.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _require_shap():
    try:
        import shap  # noqa: F401

        return True
    except ImportError:
        sys.stderr.write(
            "shap is not installed.  Install via:\n"
            "    pip install shap\n\n"
            "Then re-run this script.\n"
        )
        return False


def run(round_num: int, season: int, output: Path) -> int:
    if not _require_shap():
        return 1

    import numpy as np  # noqa: F401
    import shap
    from xgboost import XGBRegressor

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

    xgb = XGBRegressor(
        n_estimators=250, learning_rate=0.05, max_depth=3,
        random_state=42, verbosity=0,
    ).fit(X, y)

    explainer = shap.TreeExplainer(xgb)
    shap_values = explainer.shap_values(X)

    # For each driver: rank features by absolute SHAP contribution and
    # emit the top 5 features along with their signed values.
    drivers = merged["Driver"].tolist()
    rows = []
    for i, drv in enumerate(drivers):
        contributions = []
        for j, col in enumerate(feature_cols):
            contributions.append(
                {
                    "feature": col,
                    "value": float(X.iloc[i][col]),
                    "shap_contribution": float(shap_values[i][j]),
                }
            )
        contributions.sort(key=lambda c: abs(c["shap_contribution"]), reverse=True)
        rows.append(
            {
                "driver": drv,
                "predicted_lap_time_offset": float(shap_values[i].sum()),
                "top_features": contributions[:5],
            }
        )

    payload = {
        "season": season,
        "round": round_num,
        "circuit_key": gp_key,
        "base_value": float(explainer.expected_value),
        "drivers": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"✅ SHAP ablation for round {round_num} → {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("website/public/data/ablation/round_NN.json"),
        help="Output JSON path; the literal 'NN' is replaced with the "
        "zero-padded round number.",
    )
    args = parser.parse_args(argv)
    output = Path(str(args.output).replace("NN", f"{args.round:02d}"))
    return run(args.round, args.season, output)


if __name__ == "__main__":
    raise SystemExit(main())
