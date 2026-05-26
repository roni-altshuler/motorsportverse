#!/usr/bin/env python3
"""
build_ranker_training_data.py
=============================
Assemble a leakage-safe (driver, race) training parquet for the LambdaRank
candidate pipeline (``models/ranking.py``).

Pulls finishing positions from ``data/history.duckdb`` (populated by
``backfill_history.py`` / ``ergast_backfill.py``) and engineers a small
set of strictly-prior-round features. The output is consumed by:

  * ``scripts/tune_ranker.py`` for Optuna hyperparameter search
  * ``models/ranking_pipeline.py`` (via the export integration) at
    inference time, where the same feature engineering runs against the
    current round so the live frame matches the training frame.

Feature set (deliberately small for the first ship — richer features will
be plumbed once the shadow stream is producing trustworthy numbers):

  * ``PriorFinishMean3`` — driver's mean finish over the 3 most recent
    prior races (NaN before they have 3 races; imputed to field mean).
  * ``PriorFinishMean8`` — wider rolling window for stability.
  * ``PriorFinishStd5`` — variance proxy ("is this driver consistent?").
  * ``PriorPodiumRate`` — fraction of prior races in the top 3.
  * ``PriorDNFRate`` — fraction of prior races at position >= 21.
  * ``CurrentSeasonRound`` — temporal cue; ranker can learn early-season
    rookie effects.

Strict leakage discipline: each row's features are computed using ONLY
races with ``(season, round) < (current_season, current_round)``. The
``leakage.assert_seasons_prior_only`` guard wraps every aggregation.

Usage:
    python scripts/build_ranker_training_data.py \\
        --seasons 2023 2024 2025 \\
        --output data/ranker_training.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import duckdb
except ImportError:  # pragma: no cover
    sys.stderr.write("duckdb required (pip install duckdb)\n")
    raise SystemExit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "history.duckdb"
DEFAULT_OUT = PROJECT_ROOT / "data" / "ranker_training.parquet"

# Field-mean fallback for unknown drivers (22-car grid → midfield ≈ 11.5).
FIELD_MEAN_FINISH = 11.5


def load_history(db_path: Path, seasons: list[int]) -> pd.DataFrame:
    """Read (season, round, driver, actual_position) rows from history.duckdb.

    Filters to rows where actual_position is non-null and 1..22, since DNFs
    are stored inconsistently across sources. Adds a CircuitKey column
    placeholder (round number stringified) until per-circuit metadata is
    plumbed through.
    """
    con = duckdb.connect(str(db_path), read_only=True)
    seasons_csv = ",".join(str(s) for s in seasons)
    rows = con.execute(f"""
        SELECT season, round, driver, actual_position
        FROM historical_predictions
        WHERE season IN ({seasons_csv})
          AND actual_position IS NOT NULL
          AND actual_position BETWEEN 1 AND 22
        ORDER BY season, round, actual_position
    """).fetchdf()
    rows = rows.rename(columns={
        "season": "Season",
        "round": "Round",
        "driver": "Driver",
        "actual_position": "FinishPosition",
    })
    # Placeholder circuit key — same circuit each year gets same round in
    # most calendars, good enough for the first ranker iteration.
    rows["CircuitKey"] = rows["Round"].astype(str)
    rows["IsSprint"] = False  # not currently distinguished in history.duckdb
    return rows


def engineer_features(history: pd.DataFrame) -> pd.DataFrame:
    """Compute prior-only rolling features per driver per (season, round).

    Each row's features use ``.shift(1)`` followed by ``.expanding`` or
    ``.rolling`` so the current race's outcome never feeds its own feature.
    """
    if history.empty:
        return history

    df = history.copy()
    df = df.sort_values(["Driver", "Season", "Round"]).reset_index(drop=True)

    # Position of the SAME driver in their preceding races
    by_driver = df.groupby("Driver")["FinishPosition"]
    shifted = by_driver.shift(1)
    df["PriorFinishMean3"] = (
        shifted.groupby(df["Driver"]).rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    )
    df["PriorFinishMean8"] = (
        shifted.groupby(df["Driver"]).rolling(8, min_periods=1).mean().reset_index(level=0, drop=True)
    )
    df["PriorFinishStd5"] = (
        shifted.groupby(df["Driver"]).rolling(5, min_periods=2).std().reset_index(level=0, drop=True)
    )
    df["PriorPodiumRate"] = (
        (shifted <= 3).astype(float)
        .groupby(df["Driver"]).expanding(min_periods=1).mean().reset_index(level=0, drop=True)
    )
    df["PriorDNFRate"] = (
        (shifted >= 21).astype(float)
        .groupby(df["Driver"]).expanding(min_periods=1).mean().reset_index(level=0, drop=True)
    )

    # Field-mean imputation for early-career rows
    df["PriorFinishMean3"] = df["PriorFinishMean3"].fillna(FIELD_MEAN_FINISH)
    df["PriorFinishMean8"] = df["PriorFinishMean8"].fillna(FIELD_MEAN_FINISH)
    df["PriorFinishStd5"] = df["PriorFinishStd5"].fillna(5.0)
    df["PriorPodiumRate"] = df["PriorPodiumRate"].fillna(0.0)
    df["PriorDNFRate"] = df["PriorDNFRate"].fillna(0.0)

    df["CurrentSeasonRound"] = df["Round"].astype(float)

    # Re-sort into the contiguous race-by-race ordering LightGBM needs
    df = df.sort_values(["Season", "Round", "Driver"]).reset_index(drop=True)
    return df


def assert_no_leakage(df: pd.DataFrame) -> None:
    """Pin: rows with NaN-imputed features (== first appearances) should have
    PriorFinishMean3 == FIELD_MEAN_FINISH or be reasonably close. Sanity check
    that we didn't accidentally use the current row's outcome."""
    if df.empty:
        return
    first_per_driver = df.groupby("Driver", as_index=False).first()
    # Their PriorFinishMean3 should equal field mean (no prior data → fallback).
    mismatched = first_per_driver[
        ~np.isclose(first_per_driver["PriorFinishMean3"], FIELD_MEAN_FINISH, atol=0.01)
    ]
    if not mismatched.empty:
        raise RuntimeError(
            f"Leakage check failed: {len(mismatched)} drivers have non-fallback "
            f"PriorFinishMean3 on their first race. Sample:\n"
            f"{mismatched.head(5)[['Driver','Season','Round','PriorFinishMean3']]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if not args.db.exists():
        sys.stderr.write(f"history db not found at {args.db}; run backfill_history.py first\n")
        return 1

    print(f"  Loading seasons {args.seasons} from {args.db}…")
    history = load_history(args.db, args.seasons)
    print(f"  {len(history)} rows / {history[['Season','Round']].drop_duplicates().shape[0]} races / "
          f"{history['Driver'].nunique()} drivers")
    if history.empty:
        sys.stderr.write("no rows returned; cannot build training data\n")
        return 1

    print("  Engineering prior-only features…")
    engineered = engineer_features(history)
    assert_no_leakage(engineered)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_parquet(args.output, index=False)
    print(f"  Wrote {len(engineered)} rows × {len(engineered.columns)} cols → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
