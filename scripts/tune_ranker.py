#!/usr/bin/env python3
"""
tune_ranker.py
==============
Optuna search over LightGBM LambdaRank hyperparameters. Objective is the
mean NDCG@5 across all race-grouped CV folds — the same evaluator the
promotion gate will use, so a tuning win translates directly into a
shipping win.

Usage:
    python scripts/tune_ranker.py --training data/training_rows.parquet \\
                                  --target FinishPosition --trials 80

The training parquet is whatever the caller chose to assemble — typically
the output of ``f1_prediction_utils.build_training_dataset`` saved with
pandas ``.to_parquet``. The script doesn't enforce a schema beyond the
columns the ranker needs (Season, Round, Driver, the target, the feature
list).

Requires optuna, which is intentionally commented out in
``requirements-dev.txt`` because it pulls a scikit-learn pin that
conflicts with our runtime. Install ad-hoc in the f1_predictions env:

    pip install 'optuna~=4.1.0'

If optuna isn't installed the script prints a clear error and exits 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    import optuna
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "optuna is required for tune_ranker.py. Install with:\n"
        "  pip install 'optuna~=4.1.0'\n"
    )
    raise SystemExit(1)

from models.cv import RaceGroupedTimeSeriesSplit  # noqa: E402
from models.ranking import LambdaRanker, LambdaRankerConfig, build_groups  # noqa: E402


def _ndcg_at_k(ordering: np.ndarray, relevance: np.ndarray, k: int) -> float:
    """Standard NDCG@k. ``ordering`` are the predicted positions (1..N);
    ``relevance`` is the true relevance (higher = better)."""
    n = len(relevance)
    if n == 0:
        return 0.0
    # Take top-k by predicted ordering
    top_indices = np.argsort(ordering)[:k]
    gains = relevance[top_indices]
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float(np.sum(gains * discounts))
    ideal_gains = np.sort(relevance)[::-1][:k]
    ideal_discounts = 1.0 / np.log2(np.arange(2, len(ideal_gains) + 2))
    idcg = float(np.sum(ideal_gains * ideal_discounts))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


def objective(trial: optuna.Trial, X: pd.DataFrame, y: np.ndarray, groups_df: pd.DataFrame,
              rows: pd.DataFrame, target_col: str) -> float:
    cfg = LambdaRankerConfig(
        num_leaves=trial.suggest_int("num_leaves", 15, 127),
        learning_rate=trial.suggest_float("learning_rate", 1e-2, 1.5e-1, log=True),
        min_data_in_leaf=trial.suggest_int("min_data_in_leaf", 10, 80),
        feature_fraction=trial.suggest_float("feature_fraction", 0.6, 1.0),
        bagging_fraction=trial.suggest_float("bagging_fraction", 0.6, 1.0),
        bagging_freq=trial.suggest_int("bagging_freq", 1, 7),
        num_boost_round=trial.suggest_int("num_boost_round", 300, 1200),
    )
    cv = RaceGroupedTimeSeriesSplit(n_splits=4, min_train_races=20, test_size_races=4)
    fold_ndcg: list[float] = []
    for train_idx, test_idx in cv.split(X, y, groups=groups_df):
        train_rows = rows.iloc[train_idx]
        test_rows = rows.iloc[test_idx]
        train_groups = build_groups(train_rows)
        test_groups = build_groups(test_rows)
        ranker = LambdaRanker(config=cfg)
        ranker.fit(X.iloc[train_idx], y[train_idx], train_groups)
        scores = ranker.predict(X.iloc[test_idx])
        # Per-race NDCG@5 then average within fold
        per_race: list[float] = []
        start = 0
        for size in test_groups.astype(int):
            end = start + size
            slice_scores = scores[start:end]
            slice_y = y[test_idx][start:end]
            # finish-position → relevance: lower position is better
            relevance = np.clip(22.0 - np.clip(slice_y, 1, 22) + 1, 0, None)
            ordering = np.empty(size, dtype=np.int64)
            ordering[np.argsort(-slice_scores)] = np.arange(1, size + 1)
            per_race.append(_ndcg_at_k(ordering, relevance, k=5))
            start = end
        if per_race:
            fold_ndcg.append(float(np.mean(per_race)))
    if not fold_ndcg:
        return 0.0
    return float(np.mean(fold_ndcg))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True,
                        help="Parquet file with training rows (Season, Round, Driver, features, target)")
    parser.add_argument("--target", default="FinishPosition")
    parser.add_argument("--features", nargs="+", default=None,
                        help="Feature columns (default: all numeric columns except identifiers)")
    parser.add_argument("--trials", type=int, default=80)
    parser.add_argument("--output", type=Path, default=Path("reports/tune_ranker_best.json"))
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args(argv)

    rows = pd.read_parquet(args.training)
    if not {"Season", "Round", "Driver", args.target}.issubset(rows.columns):
        sys.stderr.write(f"training frame missing required columns; have {list(rows.columns)}\n")
        return 1

    if args.features is None:
        excluded = {"Season", "Round", "Driver", "Team", args.target}
        features = [c for c in rows.columns
                    if c not in excluded and pd.api.types.is_numeric_dtype(rows[c])]
    else:
        features = list(args.features)

    sort_cols = ["Season", "Round"]
    if "IsSprint" in rows.columns:
        sort_cols.append("IsSprint")
    sort_cols.append("Driver")
    rows = rows.sort_values(sort_cols).reset_index(drop=True)
    X = rows[features].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = rows[args.target].astype(float).clip(1, 22).values
    groups_df = rows[["Season", "Round"]]

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=args.seed))
    study.optimize(
        lambda trial: objective(trial, X, y, groups_df, rows, args.target),
        n_trials=args.trials,
        show_progress_bar=False,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "best_value_ndcg5": study.best_value,
        "best_params": study.best_params,
        "n_trials": args.trials,
        "features": features,
        "target": args.target,
    }
    with args.output.open("w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
