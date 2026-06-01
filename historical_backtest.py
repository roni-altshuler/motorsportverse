"""Historical backtest of the prediction system against 2024 + 2025.

Reads predicted + actual finishing positions per (season, round, driver)
from ``data/history.duckdb`` and produces per-round + per-season
accuracy metrics in the same shape as ``forward_eval`` output, so the
website's Accuracy page can render historical performance alongside
the live season.

What this measures
------------------
The ``predicted_position`` column in the historical DB is derived from
qualifying-pace based prediction at the time of the race (FastF1
session export — no future leakage). The ``actual_position`` is the
classified race result. Scoring those two columns against each other
tells us how well the qualifying-pace signal alone tracks race
outcomes — a leak-safe lower bound on what a richer ML pipeline can
achieve.

When we have additional predicted-position streams (e.g. the full
ensemble's predictions for past seasons), the same metrics can be
re-run against them by extending the DB schema. The output JSON
shape is identical so the frontend doesn't care which predictor was
used.

Usage
-----

    python historical_backtest.py --seasons 2024 2025

Output
------
    reports/historical_backtest.json                     — combined
    website/public/data/historical_backtest/<season>.json — per-season
    website/public/data/historical_backtest/<season>_round_<NN>.json
        — per-round detail (every driver's predicted-vs-actual gap)
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "history.duckdb"
REPORTS_DIR = PROJECT_ROOT / "reports"
WEB_OUT_DIR = PROJECT_ROOT / "website" / "public" / "data" / "historical_backtest"


def _load_predictions(con, season: int) -> list[dict]:
    """Return all (round, driver, predicted, actual) rows for a season."""
    cur = con.execute(
        """
        SELECT season, round, driver, predicted_position, actual_position
        FROM historical_predictions
        WHERE season = ?
          AND predicted_position IS NOT NULL
          AND actual_position IS NOT NULL
        ORDER BY round, predicted_position
        """,
        [season],
    )
    rows = cur.fetchall()
    return [
        {
            "season": r[0],
            "round": r[1],
            "driver": r[2],
            "predicted": int(r[3]),
            "actual": int(r[4]),
        }
        for r in rows
    ]


def _spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rank correlation. Returns None when undefined."""
    n = len(a)
    if n < 2:
        return None
    # Rank both arrays; since predicted + actual are already integer
    # positions we can use them as ranks directly.
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((a[i] - mean_a) ** 2 for i in range(n))
    var_b = sum((b[i] - mean_b) ** 2 for i in range(n))
    denom = math.sqrt(var_a * var_b)
    if denom == 0:
        return None
    return cov / denom


def _ndcg_at_k(predicted_order: list[str], actual_positions: dict[str, int], k: int = 5) -> float:
    """NDCG@k where relevance = max(0, (k+1) - actual_position)."""
    def gain(driver: str) -> float:
        pos = actual_positions.get(driver)
        if pos is None or pos > k:
            return 0.0
        return float(k + 1 - pos)

    dcg = 0.0
    for i, drv in enumerate(predicted_order[:k]):
        dcg += gain(drv) / math.log2(i + 2)
    ideal_order = sorted(
        actual_positions.keys(), key=lambda d: actual_positions[d]
    )
    idcg = 0.0
    for i, drv in enumerate(ideal_order[:k]):
        idcg += gain(drv) / math.log2(i + 2)
    return dcg / idcg if idcg > 0 else 0.0


def _round_metrics(rows: list[dict]) -> dict:
    """Compute the per-round metric block (matches forward_eval shape)."""
    predicted = [r["predicted"] for r in rows]
    actual = [r["actual"] for r in rows]
    n = len(rows)
    errors = [abs(p - a) for p, a in zip(predicted, actual)]
    deltas = [p - a for p, a in zip(predicted, actual)]
    sq_errors = [(p - a) ** 2 for p, a in zip(predicted, actual)]

    # Predicted top-3 and actual top-3
    predicted_by_drv = {r["driver"]: r["predicted"] for r in rows}
    actual_by_drv = {r["driver"]: r["actual"] for r in rows}
    predicted_top3 = sorted(predicted_by_drv, key=predicted_by_drv.get)[:3]
    actual_top3 = sorted(actual_by_drv, key=actual_by_drv.get)[:3]
    actual_winner = sorted(actual_by_drv, key=actual_by_drv.get)[0]
    predicted_winner = sorted(predicted_by_drv, key=predicted_by_drv.get)[0]

    podium_hits = len(set(predicted_top3) & set(actual_top3))
    exact_matches = sum(1 for p, a in zip(predicted, actual) if p == a)

    biggest_misses = sorted(
        [
            {
                "driver": r["driver"],
                "predicted": r["predicted"],
                "actual": r["actual"],
                "delta": r["predicted"] - r["actual"],
                "absDelta": abs(r["predicted"] - r["actual"]),
            }
            for r in rows
        ],
        key=lambda r: r["absDelta"],
        reverse=True,
    )[:5]

    predicted_order = sorted(
        predicted_by_drv, key=predicted_by_drv.get
    )

    return {
        "season": rows[0]["season"],
        "round": rows[0]["round"],
        "drivers_compared": n,
        "mean_position_error": float(mean(errors)),
        "median_position_error": float(sorted(errors)[n // 2]),
        "rmse_position_error": float(math.sqrt(mean(sq_errors))),
        "exact_matches": exact_matches,
        "within_3": sum(1 for e in errors if e <= 3),
        "within_5": sum(1 for e in errors if e <= 5),
        "winner_hit": predicted_winner == actual_winner,
        "podium_hits": podium_hits,
        "mean_signed_delta": float(mean(deltas)),
        "spearman_correlation": _spearman(
            [float(x) for x in predicted], [float(x) for x in actual]
        ),
        "ndcg_at_5": _ndcg_at_k(predicted_order, actual_by_drv, k=5),
        "biggest_misses": biggest_misses,
    }


def _season_summary(rounds: list[dict]) -> dict:
    if not rounds:
        return {
            "rounds_evaluated": 0,
            "season_mean_error": None,
            "season_median_error": None,
            "winner_hit_rate": None,
            "podium_hit_rate": None,
            "exact_match_rate": None,
            "within_3_rate": None,
            "within_5_rate": None,
            "mean_spearman": None,
            "mean_ndcg_at_5": None,
        }
    maes = [r["mean_position_error"] for r in rounds]
    n_drivers = [r["drivers_compared"] for r in rounds]
    podium_total_slots = 3 * len(rounds)
    return {
        "rounds_evaluated": len(rounds),
        "season_mean_error": float(round(mean(maes), 3)),
        "season_median_error": float(
            round(sorted([r["median_position_error"] for r in rounds])[len(rounds) // 2], 3)
        ),
        "winner_hit_rate": float(
            round(sum(1 for r in rounds if r["winner_hit"]) / len(rounds), 3)
        ),
        "podium_hit_rate": float(
            round(sum(r["podium_hits"] for r in rounds) / podium_total_slots, 3)
        ),
        "exact_match_rate": float(
            round(sum(r["exact_matches"] for r in rounds) / sum(n_drivers), 3)
        ),
        "within_3_rate": float(
            round(sum(r["within_3"] for r in rounds) / sum(n_drivers), 3)
        ),
        "within_5_rate": float(
            round(sum(r["within_5"] for r in rounds) / sum(n_drivers), 3)
        ),
        "mean_spearman": float(
            round(mean([r["spearman_correlation"] for r in rounds if r["spearman_correlation"] is not None]), 3)
        ),
        "mean_ndcg_at_5": float(
            round(mean([r["ndcg_at_5"] for r in rounds]), 3)
        ),
    }


def _per_track_summary(rounds: list[dict], track_lookup: dict) -> list[dict]:
    """Group rounds by circuit (best-effort via round number)."""
    out: list[dict] = []
    for r in rounds:
        season = r["season"]
        rnd = r["round"]
        circuit = track_lookup.get((season, rnd), f"R{rnd:02d}")
        out.append(
            {
                "season": season,
                "round": rnd,
                "circuit": circuit,
                "mae": r["mean_position_error"],
                "podium_hits": r["podium_hits"],
                "winner_hit": r["winner_hit"],
                "spearman": r["spearman_correlation"],
                "ndcg_at_5": r["ndcg_at_5"],
            }
        )
    return out


def _per_driver_summary(rows_by_season: dict[int, list[dict]]) -> list[dict]:
    """Aggregate per-driver predicted-vs-actual accuracy across the seasons."""
    bucket: dict[str, list[int]] = defaultdict(list)
    rounds_for_driver: dict[str, int] = defaultdict(int)
    for season, rows in rows_by_season.items():
        for r in rows:
            bucket[r["driver"]].append(abs(r["predicted"] - r["actual"]))
            rounds_for_driver[r["driver"]] += 1
    out = []
    for drv, errors in bucket.items():
        out.append(
            {
                "driver": drv,
                "rounds": rounds_for_driver[drv],
                "mae": float(round(mean(errors), 3)),
                "within_3_rate": float(
                    round(sum(1 for e in errors if e <= 3) / len(errors), 3)
                ),
            }
        )
    out.sort(key=lambda r: r["mae"])
    return out


def _reliability_buckets(rows_by_round: list[dict], bins: int = 10) -> list[dict]:
    """Coarse calibration check: for each predicted-position decile,
    what fraction of drivers actually finished inside that decile?

    Uses |predicted - actual| / max(predicted, actual) as a "miss rate"
    proxy; bucket by predicted bin and report the empirical proximity
    rate (1 - mean miss rate).
    """
    if not rows_by_round:
        return []
    all_rows = [row for rd in rows_by_round for row in rd.get("__rows__", [])]
    if not all_rows:
        return []
    max_pos = max(r["predicted"] for r in all_rows)
    buckets: list[dict] = []
    edges = [int(round(i * max_pos / bins)) for i in range(bins + 1)]
    for i in range(bins):
        lo, hi = edges[i] + 1, edges[i + 1]
        bucket_rows = [r for r in all_rows if lo <= r["predicted"] <= hi]
        if not bucket_rows:
            continue
        proximity = mean(
            1.0 - abs(r["predicted"] - r["actual"]) / max(r["predicted"], r["actual"], 1)
            for r in bucket_rows
        )
        buckets.append(
            {
                "predicted_lo": lo,
                "predicted_hi": hi,
                "samples": len(bucket_rows),
                "mean_proximity": float(round(proximity, 3)),
                "mean_actual": float(
                    round(mean(r["actual"] for r in bucket_rows), 2)
                ),
            }
        )
    return buckets


def backtest(seasons: Iterable[int]) -> dict:
    seasons = list(seasons)
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"history.duckdb not found at {DB_PATH}; run ergast_backfill.py first"
        )
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows_by_season: dict[int, list[dict]] = {}
    for season in seasons:
        rows_by_season[season] = _load_predictions(con, season)

    season_blocks = []
    all_round_blocks_with_rows = []
    for season in seasons:
        rows = rows_by_season[season]
        rounds_grouped: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            rounds_grouped[r["round"]].append(r)
        round_blocks = []
        for rnd in sorted(rounds_grouped):
            block = _round_metrics(rounds_grouped[rnd])
            block["__rows__"] = rounds_grouped[rnd]
            round_blocks.append(block)
        public_rounds = [
            {k: v for k, v in b.items() if k != "__rows__"} for b in round_blocks
        ]
        season_blocks.append(
            {
                "season": season,
                "rounds": public_rounds,
                "summary": _season_summary(public_rounds),
            }
        )
        all_round_blocks_with_rows.extend(round_blocks)

    # Combined across all requested seasons
    all_rows_flat = [r for season in seasons for r in rows_by_season[season]]
    rows_by_season_flat = {s: rows_by_season[s] for s in seasons}
    overall_per_driver = _per_driver_summary(rows_by_season_flat)
    overall_reliability = _reliability_buckets(all_round_blocks_with_rows)

    return {
        "seasons": seasons,
        "perSeason": season_blocks,
        "perDriver": overall_per_driver,
        "reliability": overall_reliability,
        "totalRows": len(all_rows_flat),
        "source": "data/history.duckdb",
        "scoring": "qualifying-pace baseline vs actual classification",
    }


def write_outputs(payload: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORTS_DIR / "historical_backtest.json").open("w") as fh:
        json.dump(payload, fh, indent=2)
    with (WEB_OUT_DIR / "summary.json").open("w") as fh:
        # Slim version for the website: drop the rows-level detail
        # to keep payload sub-150KB.
        light = {
            **payload,
            "perSeason": [
                {
                    "season": s["season"],
                    "summary": s["summary"],
                    "rounds": [
                        {
                            k: v
                            for k, v in r.items()
                            if k != "biggest_misses"
                        }
                        for r in s["rounds"]
                    ],
                }
                for s in payload["perSeason"]
            ],
        }
        json.dump(light, fh, indent=2)
    # Per-season detail (full)
    for s in payload["perSeason"]:
        path = WEB_OUT_DIR / f"{s['season']}.json"
        with path.open("w") as fh:
            json.dump(s, fh, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2024, 2025],
        help="Seasons to backtest. Defaults to 2024 and 2025.",
    )
    args = parser.parse_args(argv)

    payload = backtest(args.seasons)
    write_outputs(payload)

    print(f"📊 Historical backtest written for seasons: {args.seasons}")
    for s in payload["perSeason"]:
        summary = s["summary"]
        n = summary["rounds_evaluated"]
        if not n:
            print(f"  {s['season']}: no rounds scored")
            continue
        print(
            f"  {s['season']}: n={n}  MAE={summary['season_mean_error']:.2f}  "
            f"Spearman={summary['mean_spearman']:.3f}  "
            f"podium-hits={summary['podium_hit_rate']:.1%}  "
            f"winner-hits={summary['winner_hit_rate']:.1%}"
        )
    print("📝 Written reports/historical_backtest.json + per-season files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
