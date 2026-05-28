"""FastF1-driven historical backfill for the 2018-2022 seasons.

Goal of this script
-------------------
Phase 9 produced strong evidence that the current production model
(Phase 7 static) is data-sensitive but architecture-saturated. Adding
one season of training data lifted winner-hit by ~6pp. Five more
seasons of equivalent data should push the model substantially
further.

This script reads the 2018-2022 race weekends from the FastF1 cache
and inserts rows into ``data/history.duckdb`` that match the existing
``historical_predictions`` schema:

* ``predicted_position`` — qualifying grid position (1..N)
* ``actual_position`` — race finishing position (1..N)
* ``predicted_lap_time`` — driver's best Q lap time in seconds
* ``source`` — ``"fastf1_backfill"``

The same TLA codes ("VER", "HAM", ...) FastF1 emits are already the
DB's driver-key format, so no driver normalisation is needed.

Restart-safety
--------------
The DB primary key is ``(season, round, driver)``. We use
``INSERT OR REPLACE`` so the script can be re-run safely; partial
runs leave the DB in a clean idempotent state.

Usage
-----
::

    # Sanity-test one season (~3-5 min from a warm cache):
    python backfill_2018_2022.py --seasons 2022

    # Full backfill 2018-2022 (~15-25 min from a warm cache):
    python backfill_2018_2022.py --seasons 2018 2019 2020 2021 2022

    # Dry run (no DB writes):
    python backfill_2018_2022.py --seasons 2022 --dry-run

Idempotency
-----------
Re-running on the same season replaces existing rows rather than
duplicating them, so it is safe to re-run after a partial failure.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

# Silence FastF1 chatter unless explicitly enabled.
warnings.filterwarnings("ignore")
for noisy in ("fastf1", "core", "req", "_api"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

import duckdb
import fastf1  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent
F1_CACHE_DIR = PROJECT_ROOT / "f1_cache"
DB_PATH = PROJECT_ROOT / "data" / "history.duckdb"


@dataclass
class BackfillRow:
    season: int
    round: int
    driver: str
    predicted_position: int | None
    actual_position: int | None
    predicted_lap_time: float | None
    source: str = "fastf1_backfill"


def _enable_cache() -> None:
    F1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(F1_CACHE_DIR))


def _safe_load(year: int, round_: int, session_name: str):
    try:
        session = fastf1.get_session(year, round_, session_name)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        return session
    except Exception:
        return None


def _grid_and_q_lap(year: int, round_: int) -> dict[str, dict[str, float | int | None]]:
    """Return per-driver grid position + best Q lap time from the Q session."""
    out: dict[str, dict[str, float | int | None]] = {}
    q = _safe_load(year, round_, "Q")
    if q is None:
        return out
    results = getattr(q, "results", None)
    if results is None or len(results) == 0:
        return out
    df = results
    laps = q.laps if hasattr(q, "laps") and q.laps is not None else pd.DataFrame()
    # Best lap per driver in Q.
    if not laps.empty and "LapTime" in laps.columns:
        with_time = laps[laps["LapTime"].notna()].copy()
        if not with_time.empty:
            with_time["LapTimeSec"] = with_time["LapTime"].dt.total_seconds()
            best_by_driver = with_time.groupby("Driver")["LapTimeSec"].min().to_dict()
        else:
            best_by_driver = {}
    else:
        best_by_driver = {}
    for _, row in df.iterrows():
        tla = str(row.get("Abbreviation") or row.get("Driver") or "").strip()
        if not tla:
            continue
        grid = row.get("GridPosition")
        position = row.get("Position")
        # GridPosition is the race grid (may carry penalties applied
        # post-qualifying). Falling back to qualifying Position when
        # GridPosition isn't populated.
        rank: int | None
        try:
            if grid is not None and not pd.isna(grid) and float(grid) > 0:
                rank = int(grid)
            elif position is not None and not pd.isna(position) and float(position) > 0:
                rank = int(position)
            else:
                rank = None
        except (TypeError, ValueError):
            rank = None
        best_lap = best_by_driver.get(tla)
        out[tla] = {
            "predicted_position": rank,
            "predicted_lap_time": float(best_lap) if best_lap is not None else None,
        }
    return out


def _race_results(year: int, round_: int) -> dict[str, int | None]:
    """Return per-driver actual finishing position from the Race session."""
    out: dict[str, int | None] = {}
    r = _safe_load(year, round_, "R")
    if r is None:
        return out
    results = getattr(r, "results", None)
    if results is None or len(results) == 0:
        return out
    for _, row in results.iterrows():
        tla = str(row.get("Abbreviation") or row.get("Driver") or "").strip()
        if not tla:
            continue
        pos = row.get("Position")
        try:
            actual: int | None
            if pos is not None and not pd.isna(pos) and float(pos) > 0:
                actual = int(pos)
            else:
                actual = None
        except (TypeError, ValueError):
            actual = None
        out[tla] = actual
    return out


def backfill_round(year: int, round_: int) -> list[BackfillRow]:
    grid = _grid_and_q_lap(year, round_)
    finish = _race_results(year, round_)
    drivers = set(grid) | set(finish)
    rows: list[BackfillRow] = []
    for drv in sorted(drivers):
        g = grid.get(drv, {})
        rows.append(
            BackfillRow(
                season=year,
                round=round_,
                driver=drv,
                predicted_position=g.get("predicted_position"),
                actual_position=finish.get(drv),
                predicted_lap_time=g.get("predicted_lap_time"),
            )
        )
    return rows


def backfill_season(year: int, max_rounds: int = 24) -> list[BackfillRow]:
    all_rows: list[BackfillRow] = []
    for r in range(1, max_rounds + 1):
        rows = backfill_round(year, r)
        if not rows:
            print(f"  [{year} R{r:02d}] no usable data — stopping season")
            break
        complete = sum(
            1 for x in rows
            if x.predicted_position is not None and x.actual_position is not None
        )
        all_rows.extend(rows)
        print(f"  [{year} R{r:02d}] {len(rows)} drivers ({complete} complete)")
    return all_rows


def upsert_rows(rows: list[BackfillRow], db_path: Path) -> int:
    """INSERT OR REPLACE rows into historical_predictions; return count written."""
    if not rows:
        return 0
    df = pd.DataFrame([r.__dict__ for r in rows])
    con = duckdb.connect(str(db_path))
    try:
        # Use a registered view + INSERT OR REPLACE for idempotency.
        con.register("incoming", df)
        con.execute(
            """
            INSERT OR REPLACE INTO historical_predictions (
                season, round, driver, predicted_position,
                actual_position, predicted_lap_time, source
            )
            SELECT season, round, driver, predicted_position,
                   actual_position, predicted_lap_time, source
            FROM incoming
            """
        )
        con.unregister("incoming")
    finally:
        con.close()
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2022],
        help="Seasons to backfill (default: just 2022, the sanity-test single season)",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=24,
        help="Cap rounds per season (default 24)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract but don't write to the DB",
    )
    parser.add_argument(
        "--db", default=str(DB_PATH),
        help="Path to history.duckdb",
    )
    args = parser.parse_args(argv)

    _enable_cache()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist — create the DB first")
        return 1

    total_written = 0
    for year in args.seasons:
        print(f"\n=== Backfilling {year} ===")
        rows = backfill_season(year, max_rounds=args.max_rounds)
        if args.dry_run:
            print(f"  [dry-run] would write {len(rows)} rows for {year}")
            continue
        written = upsert_rows(rows, db_path)
        total_written += written
        print(f"  wrote {written} rows for {year}")

    if not args.dry_run:
        print(f"\nTotal rows written: {total_written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
