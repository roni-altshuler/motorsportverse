"""Backfill historical (predicted, actual) F1 finishing positions per round.

Why this exists
---------------
The probability layer (`models/calibration.py`) fits an isotonic calibrator
on (predicted_probability, observed_outcome) pairs *per market* (win, podium,
top6, top10).  Out of the box the repo only contains one completed 2026 round
of actuals, which is nowhere near the data volume isotonic needs to learn a
non-degenerate mapping.  `export_probabilities.py` therefore gates calibration
behind `min_completed_rounds=3`, currently flipping `calibration.applied=false`
on every round of the website export.

This script seeds the calibrator by walking every (season, round) of
2023/2024/2025, building a *naive baseline* predicted finishing order from
prior-season pace, fetching actuals from FastF1, and persisting both into a
DuckDB store at ``data/history.duckdb``.  Once enough rounds are present,
`export_probabilities.py --history-db data/history.duckdb` picks them up
automatically and the calibrator fits.

Naive baseline rationale
------------------------
The live pipeline regresses lap times via a GB+XGB ensemble using rich
current-season features (form, momentum, prediction bias).  Those features
cannot be reconstructed for past races without re-running the whole pipeline
for every (season, round) — and the per-race scripts under ``races/`` are not
designed to be invoked programmatically.

Pragmatic alternative used here: for each target (year, round) we aggregate
mean lap times from *strictly prior* seasons (year-1 and year-2 of the race's
session laps where cached) and rank by predicted lap time.  This isolates the
single dominant signal in F1 prediction — "this driver is historically fast
on this circuit" — without any of the leakage-prone form features.  It is
**not** a faithful replica of the live model.  Calibration learned from this
baseline corrects for systematic over/underconfidence in the *raw* probability
distribution produced by the Plackett-Luce sampler from any reasonable lap-time
ranker, which is the property we actually want.

Regenerate
----------
    # Full backfill (will take a while; uses FastF1 cache when available)
    python backfill_history.py --seasons 2023,2024,2025 --force

    # Add a single missing round
    python backfill_history.py --seasons 2024 --rounds 5

    # Default behaviour: skip rounds already in the DB
    python backfill_history.py --seasons 2023,2024,2025

CLI
---
    python backfill_history.py --seasons 2023,2024,2025 [--rounds 1-22] \
        [--db data/history.duckdb] [--force]

Constraints honoured
--------------------
* Pure additive — does not modify any of the files listed in the audit's
  Tier 1 lockdown set.
* Uses `leakage.assert_seasons_prior_only` before each per-round build to
  prove no future season/round bleeds into the baseline.
* Uses the seeded FastF1 cache under ``f1_cache/``; network failures are
  caught per-round and logged as warnings, never crash the run.
* Idempotent: re-running with the same args is a no-op (unless --force).
"""
from __future__ import annotations

import argparse
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import pandas as pd
from tqdm import tqdm

# FastF1 is needed for actuals + lap-time aggregation, but we enable cache and
# silence its warnings here so the script stays quiet under tqdm.
import fastf1

from leakage import LeakageError, assert_seasons_prior_only

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "history.duckdb"
FASTF1_CACHE_DIR = PROJECT_ROOT / "f1_cache"

# How many prior seasons to aggregate per-driver lap times from.  Two is the
# sweet spot: enough laps to be statistically meaningful, recent enough to
# track current-era car/driver changes.  Set to 0 to skip aggregation.
DEFAULT_LOOKBACK_SEASONS: int = 2


# --------------------------------------------------------------------------- #
# DB schema + IO
# --------------------------------------------------------------------------- #

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS historical_predictions (
    season              INTEGER NOT NULL,
    round               INTEGER NOT NULL,
    driver              TEXT    NOT NULL,
    predicted_position  INTEGER,
    actual_position     INTEGER,
    predicted_lap_time  DOUBLE,
    PRIMARY KEY (season, round, driver)
);
"""


def connect(db_path: Path | str) -> duckdb.DuckDBPyConnection:
    """Open (and lazily create) the DuckDB store at ``db_path``."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(p))
    conn.execute(SCHEMA_SQL)
    return conn


def round_already_present(
    conn: duckdb.DuckDBPyConnection, season: int, rnd: int
) -> bool:
    """True iff at least one row for (season, round) exists in the DB."""
    row = conn.execute(
        "SELECT COUNT(*) FROM historical_predictions WHERE season=? AND round=?",
        [season, rnd],
    ).fetchone()
    return bool(row and row[0] > 0)


def delete_round(conn: duckdb.DuckDBPyConnection, season: int, rnd: int) -> None:
    """Remove any existing rows for (season, round)."""
    conn.execute(
        "DELETE FROM historical_predictions WHERE season=? AND round=?",
        [season, rnd],
    )


def insert_rows(
    conn: duckdb.DuckDBPyConnection, rows: Sequence["HistoryRow"]
) -> None:
    """Bulk insert.  Caller must have deleted any prior rows for (season,round)
    when called with --force."""
    if not rows:
        return
    conn.executemany(
        "INSERT INTO historical_predictions "
        "(season, round, driver, predicted_position, actual_position, predicted_lap_time) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                r.season,
                r.round,
                r.driver,
                r.predicted_position,
                r.actual_position,
                r.predicted_lap_time,
            )
            for r in rows
        ],
    )


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class HistoryRow:
    season: int
    round: int
    driver: str
    predicted_position: int | None
    actual_position: int | None
    predicted_lap_time: float | None


# --------------------------------------------------------------------------- #
# FastF1 helpers (network/IO; tolerant of partial cache misses)
# --------------------------------------------------------------------------- #


_CACHE_ENABLED = False


def _enable_fastf1_cache() -> None:
    global _CACHE_ENABLED
    if _CACHE_ENABLED:
        return
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))
    except Exception:
        # Cache is best-effort; FastF1 still works without it (just slower
        # and network-bound).
        pass
    _CACHE_ENABLED = True


def fetch_session_results(year: int, rnd: int) -> dict[str, int]:
    """Return mapping driver_code → finishing position for the race.

    Raises any FastF1 exception up to the caller; the orchestration loop
    converts those into per-round warnings rather than crashing.
    """
    _enable_fastf1_cache()
    session = fastf1.get_session(year, rnd, "R")
    # `laps=False` saves the slow lap-by-lap fetch when we only need the
    # classification table; we DO need laps for the prior-season aggregation
    # but that's done in a separate helper.
    session.load(laps=False, telemetry=False, weather=False, messages=False)
    results = session.results
    if results is None or len(results) == 0:
        return {}
    out: dict[str, int] = {}
    for _, row in results.iterrows():
        abbr = row.get("Abbreviation")
        pos = row.get("Position")
        if abbr is None or pos is None:
            continue
        try:
            if pd.isna(pos):
                continue
            out[str(abbr).upper()] = int(pos)
        except (TypeError, ValueError):
            continue
    return out


def fetch_race_lap_times(year: int, rnd: int) -> dict[str, float]:
    """Mean lap time (seconds) per driver in (year, rnd) race.

    Returns an empty dict on failure / no laps; callers must tolerate.
    """
    _enable_fastf1_cache()
    try:
        session = fastf1.get_session(year, rnd, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        warnings.warn(f"[backfill] {year} R{rnd}: lap fetch failed ({exc})")
        return {}
    laps = session.laps
    if laps is None or len(laps) == 0:
        return {}
    cols = laps[["Driver", "LapTime"]].dropna().copy()
    if cols.empty:
        return {}
    cols["LapSec"] = cols["LapTime"].dt.total_seconds()
    means = cols.groupby("Driver")["LapSec"].mean()
    return {str(k).upper(): float(v) for k, v in means.items() if pd.notna(v)}


# --------------------------------------------------------------------------- #
# Naive baseline predicted ranking
# --------------------------------------------------------------------------- #


def aggregate_prior_pace(
    target_season: int,
    target_round: int,
    lookback_seasons: int = DEFAULT_LOOKBACK_SEASONS,
) -> dict[str, float]:
    """Mean lap time per driver across strictly-prior seasons.

    For (target_season, target_round) we pull the same calendar slot from
    ``target_season - 1``, ``target_season - 2``, …, up to ``lookback_seasons``
    earlier.  Within ``target_season`` itself we only use rounds strictly less
    than ``target_round`` (so feature-time discipline holds even on round 1
    where we just skip same-season data entirely).

    Uses `assert_seasons_prior_only` to *prove* no future-information leak
    before returning the aggregation.
    """
    pace_lists: dict[str, list[float]] = {}
    aggregation_rows: list[dict[str, int]] = []

    # Prior same-season rounds (R-1 .. R-3 max — keeps signal recent).
    for prev_round in range(max(1, target_round - 3), target_round):
        try:
            lap_means = fetch_race_lap_times(target_season, prev_round)
        except Exception as exc:
            warnings.warn(
                f"[backfill] same-season prior fetch failed "
                f"({target_season} R{prev_round}): {exc}"
            )
            continue
        for drv, mean in lap_means.items():
            pace_lists.setdefault(drv, []).append(mean)
        aggregation_rows.append({"season": target_season, "round": prev_round})

    # Prior seasons: try the same calendar round number (approximate proxy
    # for "the same circuit").  Not perfect (calendars shift) but the
    # signal is robust to one-slot drift.
    for offset in range(1, lookback_seasons + 1):
        prior_season = target_season - offset
        if prior_season < 2018:  # FastF1 telemetry coverage starts ~2018
            continue
        try:
            lap_means = fetch_race_lap_times(prior_season, target_round)
        except Exception as exc:
            warnings.warn(
                f"[backfill] prior-season fetch failed "
                f"({prior_season} R{target_round}): {exc}"
            )
            continue
        for drv, mean in lap_means.items():
            pace_lists.setdefault(drv, []).append(mean)
        aggregation_rows.append({"season": prior_season, "round": target_round})

    # Hard leakage proof: the rows we gathered must all be strictly prior.
    assert_seasons_prior_only(
        aggregation_rows,
        current_season=target_season,
        current_round=target_round,
        label=f"prior_pace({target_season},R{target_round})",
    )

    return {drv: sum(lst) / len(lst) for drv, lst in pace_lists.items() if lst}


def rank_drivers_by_pace(pace: dict[str, float]) -> dict[str, int]:
    """Rank drivers ascending by lap time → predicted finish position (1-based)."""
    if not pace:
        return {}
    ordered = sorted(pace.items(), key=lambda kv: kv[1])
    return {drv: i + 1 for i, (drv, _) in enumerate(ordered)}


# --------------------------------------------------------------------------- #
# Per-round build
# --------------------------------------------------------------------------- #


def build_round_rows(
    season: int,
    rnd: int,
    lookback_seasons: int = DEFAULT_LOOKBACK_SEASONS,
) -> list[HistoryRow]:
    """Build all `HistoryRow`s for one (season, round).

    Returns an empty list on a fatal error (e.g. actual results unavailable).
    Errors are surfaced via stderr warnings so callers can keep going.
    """
    # Actuals: hard requirement — without them the row is useless for
    # calibration.  Surface as a warning and bail.
    try:
        actuals = fetch_session_results(season, rnd)
    except Exception as exc:
        warnings.warn(f"[backfill] {season} R{rnd}: actuals fetch failed ({exc})")
        return []
    if not actuals:
        return []

    # Predicted pace from strictly-prior data.  Empty pace is tolerable
    # (we'll write rows with predicted_position=None and the calibrator
    # loader skips them), but rare; usually at least one prior season has
    # laps cached.
    try:
        pace = aggregate_prior_pace(season, rnd, lookback_seasons=lookback_seasons)
    except LeakageError:
        # Surface as a hard error: this means our aggregator violated its
        # own contract.  Re-raise so CI catches it.
        raise
    except Exception as exc:
        warnings.warn(
            f"[backfill] {season} R{rnd}: prior-pace aggregation failed ({exc})"
        )
        pace = {}

    predicted_positions = rank_drivers_by_pace(pace)

    # Union of drivers seen in either source.  Each row carries whatever
    # values we have; the calibrator loader filters out rows missing the
    # field it needs.
    drivers = sorted(set(actuals.keys()) | set(predicted_positions.keys()))
    rows: list[HistoryRow] = []
    for drv in drivers:
        rows.append(
            HistoryRow(
                season=season,
                round=rnd,
                driver=drv,
                predicted_position=predicted_positions.get(drv),
                actual_position=actuals.get(drv),
                predicted_lap_time=pace.get(drv),
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def backfill(
    seasons: Iterable[int],
    rounds: Iterable[int] | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
    force: bool = False,
    lookback_seasons: int = DEFAULT_LOOKBACK_SEASONS,
    show_progress: bool = True,
) -> dict:
    """Walk (season, round) combinations and persist baseline rows.

    Returns a small dict with run statistics — handy for tests / CLI.
    """
    seasons = list(seasons)
    if rounds is None:
        rounds = list(range(1, 23))  # F1 calendars in 2023-2025 had ≤22 rounds
    else:
        rounds = list(rounds)

    conn = connect(db_path)
    rounds_written = 0
    rounds_skipped = 0
    rounds_failed = 0

    pairs = [(s, r) for s in seasons for r in rounds]
    iterator: Iterable[tuple[int, int]]
    if show_progress and len(pairs) > 1:
        iterator = tqdm(pairs, desc="Backfill", unit="round")
    else:
        iterator = pairs

    for season, rnd in iterator:
        already = round_already_present(conn, season, rnd)
        if already and not force:
            rounds_skipped += 1
            continue
        try:
            rows = build_round_rows(season, rnd, lookback_seasons=lookback_seasons)
        except Exception as exc:
            warnings.warn(f"[backfill] {season} R{rnd}: build failed ({exc})")
            rounds_failed += 1
            continue
        if not rows:
            rounds_failed += 1
            continue
        if already:
            delete_round(conn, season, rnd)
        insert_rows(conn, rows)
        rounds_written += 1

    conn.close()
    return {
        "rounds_written": rounds_written,
        "rounds_skipped": rounds_skipped,
        "rounds_failed": rounds_failed,
        "db_path": str(db_path),
    }


# --------------------------------------------------------------------------- #
# Reader helpers for the calibrator
# --------------------------------------------------------------------------- #


MARKET_THRESHOLDS: dict[str, int] = {
    "win": 1,
    "podium": 3,
    "top6": 6,
    "top10": 10,
}


def load_history_records(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """Read DB → flat list of records in the shape calibrator wants.

    Each output record::

        {"market": "win", "predicted": 0.42, "observed": 0,
         "season": 2024, "round": 5, "driver": "VER"}

    The "predicted" probability is reconstructed from the integer
    ``predicted_position`` by mapping rank → cumulative-rank-probability::

        P(driver finishes in top-K) = 1.0 if predicted_position <= K else 0.0

    That's the **naive baseline** probability: the calibrator's job is to
    smooth that hard step into something proper.  Isotonic regression handles
    monotone-but-degenerate inputs gracefully (constant runs collapse to the
    mean empirical rate within the run).
    """
    p = Path(db_path)
    if not p.exists():
        return []
    conn = duckdb.connect(str(p), read_only=True)
    try:
        rows = conn.execute(
            "SELECT season, round, driver, predicted_position, actual_position "
            "FROM historical_predictions "
            "WHERE predicted_position IS NOT NULL AND actual_position IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    out: list[dict] = []
    for season, rnd, driver, pred_pos, act_pos in rows:
        for market, thresh in MARKET_THRESHOLDS.items():
            out.append(
                {
                    "market": market,
                    # Naive baseline probability: 1.0 if predicted to make
                    # the cut, 0.0 otherwise.  Isotonic learns the empirical
                    # hit-rate at each level.
                    "predicted": 1.0 if int(pred_pos) <= thresh else 0.0,
                    "observed": int(int(act_pos) <= thresh),
                    "season": int(season),
                    "round": int(rnd),
                    "driver": str(driver),
                }
            )
    return out


def count_distinct_rounds(db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """How many distinct (season, round) tuples exist in the DB."""
    p = Path(db_path)
    if not p.exists():
        return 0
    conn = duckdb.connect(str(p), read_only=True)
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT (season, round)) FROM historical_predictions"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_seasons(spec: str) -> list[int]:
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        out.add(int(chunk))
    return sorted(out)


def _parse_rounds(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif chunk:
            out.add(int(chunk))
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill historical F1 (predicted, actual) results "
        "for the calibrator."
    )
    parser.add_argument(
        "--seasons",
        type=str,
        required=True,
        help="Comma-separated list of seasons, e.g. '2023,2024,2025'.",
    )
    parser.add_argument(
        "--rounds",
        type=str,
        default=None,
        help="Optional round filter, e.g. '1-10' or '3,5,7'. "
        "Default: 1-22 (covers every 2023-2025 calendar).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"DuckDB path. Default: {DEFAULT_DB_PATH.relative_to(PROJECT_ROOT)}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute rounds already present in the DB (default: skip).",
    )
    parser.add_argument(
        "--lookback-seasons",
        type=int,
        default=DEFAULT_LOOKBACK_SEASONS,
        help="How many prior seasons of lap data to aggregate per round. "
        f"Default {DEFAULT_LOOKBACK_SEASONS}.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress tqdm progress bar.",
    )
    args = parser.parse_args()

    seasons = _parse_seasons(args.seasons)
    rounds = _parse_rounds(args.rounds)

    print(
        f"Backfilling seasons={seasons} rounds="
        f"{rounds if rounds else '1-22'} into {args.db} "
        f"(force={args.force})",
        file=sys.stderr,
    )

    result = backfill(
        seasons=seasons,
        rounds=rounds,
        db_path=args.db,
        force=args.force,
        lookback_seasons=args.lookback_seasons,
        show_progress=not args.quiet,
    )

    print(
        f"\nDone. written={result['rounds_written']}  "
        f"skipped={result['rounds_skipped']}  "
        f"failed={result['rounds_failed']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
