#!/usr/bin/env python3
"""
export_ranker_predictions.py
============================
Runs the ``models.ranking_pipeline`` candidate stream against the
assembled training parquet and writes a candidate JSON beside the
production output.

This is the SHADOW STREAM — production predictions written by
``export_website_data.py`` are NOT touched. The output lives at
``website/public/data/probabilities/round_NN_candidate.json``. The
promotion gate (``promotion_decision.py``) compares the streams on
forward-eval folds and decides when the candidate is allowed to ship live.

Usage:
    # Build training data first (idempotent)
    python scripts/build_ranker_training_data.py

    # Predict the next race using all available history
    python scripts/export_ranker_predictions.py --round 7

    # Predict a specific past race (for forward-eval comparison)
    python scripts/export_ranker_predictions.py --round 6 --season 2025
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.cv import RaceGroupedTimeSeriesSplit  # noqa: E402
from models.ranking import LambdaRankerConfig  # noqa: E402
from models.ranking_pipeline import train_and_predict_next_round  # noqa: E402

DEFAULT_TRAINING = PROJECT_ROOT / "data" / "ranker_training.parquet"
DEFAULT_PROB_DIR = PROJECT_ROOT / "website" / "public" / "data" / "probabilities"
DEFAULT_SEASON_JSON = PROJECT_ROOT / "website" / "public" / "data" / "season.json"

FEATURE_COLS = [
    "PriorFinishMean3",
    "PriorFinishMean8",
    "PriorFinishStd5",
    "PriorPodiumRate",
    "PriorDNFRate",
    "CurrentSeasonRound",
]


def _build_next_round_rows(history: pd.DataFrame, season: int, current_round: int) -> pd.DataFrame:
    """Construct the inference frame for an upcoming race.

    Uses the same prior-only feature engineering that ``build_ranker_training_data``
    applied. We re-derive per-driver features here so we don't depend on
    the upcoming row already existing in history.
    """
    drivers = sorted(history["Driver"].dropna().unique().tolist())
    rows = []
    for drv in drivers:
        prior = history[(history["Driver"] == drv) &
                        ((history["Season"] < season) |
                         ((history["Season"] == season) & (history["Round"] < current_round)))]
        prior = prior.sort_values(["Season", "Round"])
        finishes = prior["FinishPosition"].astype(float).to_numpy()
        finishes = finishes[np.isfinite(finishes)]
        if len(finishes) == 0:
            mean3 = mean8 = 11.5
            std5 = 5.0
            podium_rate = 0.0
            dnf_rate = 0.0
        else:
            mean3 = float(np.mean(finishes[-3:]))
            mean8 = float(np.mean(finishes[-8:]))
            std5 = float(np.std(finishes[-5:])) if len(finishes) >= 2 else 5.0
            podium_rate = float(np.mean(finishes <= 3))
            dnf_rate = float(np.mean(finishes >= 21))
        rows.append({
            "Season": season,
            "Round": current_round,
            "Driver": drv,
            "PriorFinishMean3": mean3,
            "PriorFinishMean8": mean8,
            "PriorFinishStd5": std5,
            "PriorPodiumRate": podium_rate,
            "PriorDNFRate": dnf_rate,
            "CurrentSeasonRound": float(current_round),
            "IsSprint": False,
        })
    return pd.DataFrame(rows)


def _restrict_to_priors(history: pd.DataFrame, season: int, current_round: int) -> pd.DataFrame:
    """Return only rows strictly prior to (season, current_round). This is
    the leakage guard — the ranker only sees races that have already happened."""
    mask = (history["Season"] < season) | (
        (history["Season"] == season) & (history["Round"] < current_round)
    )
    return history[mask].copy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--round", type=int, required=True,
                        help="Round to predict (1-22 typical)")
    parser.add_argument("--season", type=int, default=None,
                        help="Season year (defaults to value in season.json)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON path (default: <prob_dir>/round_NN_candidate.json)")
    parser.add_argument("--n-splits", type=int, default=3)
    args = parser.parse_args(argv)

    if not args.training.exists():
        sys.stderr.write(
            f"training parquet not found at {args.training}; "
            "run scripts/build_ranker_training_data.py first\n"
        )
        return 1

    season = args.season
    if season is None:
        if DEFAULT_SEASON_JSON.exists():
            season = int(json.loads(DEFAULT_SEASON_JSON.read_text())["season"])
        else:
            season = _dt.date.today().year

    history = pd.read_parquet(args.training)
    print(f"  Loaded {len(history)} historical rows / "
          f"{history[['Season','Round']].drop_duplicates().shape[0]} races")

    training_rows = _restrict_to_priors(history, season, args.round)
    if training_rows.empty:
        sys.stderr.write(
            f"no training rows strictly prior to ({season}, R{args.round})\n"
        )
        return 1

    next_round_rows = _build_next_round_rows(history, season, args.round)
    print(f"  Training on {len(training_rows)} prior rows; "
          f"predicting {len(next_round_rows)} drivers for ({season}, R{args.round})")

    result = train_and_predict_next_round(
        training_rows,
        next_round_rows,
        feature_cols=FEATURE_COLS,
        target_col="FinishPosition",
        cv_config=RaceGroupedTimeSeriesSplit(
            n_splits=args.n_splits,
            min_train_races=12,
            test_size_races=4,
        ),
        ranker_config=LambdaRankerConfig(
            num_boost_round=400,
            early_stopping_rounds=40,
        ),
    )

    payload = {
        "season": season,
        "round": args.round,
        "kind": "ranker-candidate",
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "metadata": result.metadata,
        "predictions": [
            {
                "position": int(row["predictedPosition"]),
                "driver": str(row["Driver"]),
                "rankerScore": float(row["rankerScore"]),
                "winProbability": float(result.win_probabilities.get(row["Driver"], 0.0)),
                "podiumProbability": float(result.podium_probabilities.get(row["Driver"], 0.0)),
                "top6Probability": float(result.top6_probabilities.get(row["Driver"], 0.0)),
                "top10Probability": float(result.top10_probabilities.get(row["Driver"], 0.0)),
            }
            for _, row in result.predictions.iterrows()
        ],
    }

    out = args.output or (DEFAULT_PROB_DIR / f"round_{args.round:02d}_candidate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"  Wrote {len(payload['predictions'])} predictions → {out}")
    print(f"  Plackett-Luce temperature: {result.metadata['temperature']:.3f}")
    print("  Top 3:")
    for entry in payload["predictions"][:3]:
        print(f"    P{entry['position']}  {entry['driver']:>6}  "
              f"win={entry['winProbability']:.3f}  podium={entry['podiumProbability']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
