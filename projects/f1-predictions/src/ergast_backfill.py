"""Backfill F1 historical results from the Jolpica (Ergast successor) API.

Why this exists
---------------
`backfill_history.py` is excellent for 2018→present because it uses FastF1
telemetry to reconstruct a lap-time-based naive prediction.  But FastF1 only
covers the modern era (~2018+).  We have ~70 years of F1 history sitting
untouched — every race from 1950 onward is available as plain finishing-order
data via the Jolpica API (free, no key, replaces the deprecated Ergast).

This module ingests that long-tail history into the **same** DuckDB store
(`data/history.duckdb`) used by `backfill_history.py`, tagged with a
``source`` column so downstream consumers can opt in or filter out the
results-only tier.

Tier model
----------
* **Tier 1** (``source='fastf1'``): rich rows with `predicted_lap_time` from
  prior-season FastF1 telemetry.  Written by `backfill_history.py`.
* **Tier 2** (``source='ergast'``): results-only rows with no lap-time.  The
  predicted-position proxy is the **grid position** (where Jolpica has it) —
  a reasonable naive baseline ("driver starting nth tends to finish nth-ish").
  Pre-1989 races lack qualifying data in many cases; those rows store
  ``predicted_position=NULL`` and only contribute to actuals-side queries.

The calibrator reader (`backfill_history.load_history_records`) filters out
rows where ``predicted_position IS NULL`` already, so Tier 2 rows degrade
gracefully when the prediction is unrecoverable.

Calibration impact
------------------
Tier 2 rows are valuable for the **win/podium/top10** markets because those
only need rank ↔ rank pairs.  They contribute much less to the lap-time
model in `f1_prediction_utils.py` (which uses Tier 1 features only).

Regenerate
----------
::

    # Full historical backfill — every season since 1950.  This is the
    # default; a one-time multi-season pass populates the entire long tail.
    python ergast_backfill.py --seasons 1950-2025

    # Single season
    python ergast_backfill.py --seasons 2010

    # Re-ingest, replacing existing 'ergast' rows for these seasons
    python ergast_backfill.py --seasons 1990-1999 --force

    # Quiet mode (no progress bar)
    python ergast_backfill.py --seasons 1950-2025 --quiet

CLI exit codes
--------------
* ``0`` — success (one or more rounds written, or all already present)
* ``2`` — every season failed (network down, all 5xx, schema migration error)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Iterable

import duckdb
from tqdm import tqdm

# Re-use the existing DB connection + schema, so the two backfills land in the
# same store and the calibrator picks them up automatically.
from backfill_history import (
    DEFAULT_DB_PATH,
    HistoryRow,
    connect,
    delete_round,
    round_already_present,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Jolpica is a drop-in Ergast successor at api.jolpi.ca/ergast/f1.  The legacy
# ergast.com endpoint is being deprecated; Jolpica is the community-maintained
# replacement that mirrors the same response schema.
JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"

# Soft rate limit per Jolpica docs: 4 req/sec, 500 req/h burst.  One season
# fetched at a time is well within that.
DEFAULT_PER_REQUEST_SLEEP_S = 0.30

# F1's first championship season; rows older than this are not in any
# canonical results dataset.
EARLIEST_F1_SEASON = 1950

# Default User-Agent — Jolpica logs this; including the project URL is polite.
DEFAULT_USER_AGENT = "f1_predictions/ergast_backfill (https://github.com/anonymous)"


# --------------------------------------------------------------------------- #
# Schema migration — additive, idempotent
# --------------------------------------------------------------------------- #


def ensure_source_column(conn: duckdb.DuckDBPyConnection) -> None:
    """Add the ``source`` column to ``historical_predictions`` if missing.

    DuckDB's ``ALTER TABLE ADD COLUMN`` does **not** support inline ``NOT
    NULL`` constraints (errors out with "Adding columns with constraints not
    yet supported"), but it **does** honour ``DEFAULT`` — existing rows get
    back-filled to ``'fastf1'`` automatically.  We re-assert idempotency by
    probing ``information_schema.columns`` first so this is safe to call on
    every connect.
    """
    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'historical_predictions'"
        ).fetchall()
    }
    if "source" in columns:
        return
    conn.execute(
        "ALTER TABLE historical_predictions ADD COLUMN source TEXT "
        "DEFAULT 'fastf1'"
    )


# --------------------------------------------------------------------------- #
# Jolpica API — minimal stdlib client
# --------------------------------------------------------------------------- #


def _http_get_json(url: str, user_agent: str, timeout: float = 30.0) -> dict:
    """Fetch and parse a Jolpica JSON response.

    Raises ``urllib.error.HTTPError`` on non-2xx (caller turns it into a
    warning and skips the season).  ``json.JSONDecodeError`` is propagated
    because a malformed response means the API contract changed and we want
    to know loudly.
    """
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_season_results(
    year: int,
    user_agent: str = DEFAULT_USER_AGENT,
    per_request_sleep_s: float = DEFAULT_PER_REQUEST_SLEEP_S,
) -> list[dict]:
    """Return Jolpica's ``RaceTable.Races`` list for an entire season.

    Jolpica paginates at 30 results per page by default.  A season has up to
    ~22 races but each race can have ≥20 results, so we set ``limit=1000`` to
    return everything in a single page when possible.  If the season has more
    than 1000 result rows (very rare in modern era, possible mid-century with
    DNS-heavy seasons), we paginate via ``offset``.
    """
    races: list[dict] = []
    offset = 0
    limit = 1000
    while True:
        url = f"{JOLPICA_BASE_URL}/{year}/results.json?limit={limit}&offset={offset}"
        try:
            payload = _http_get_json(url, user_agent=user_agent)
        except urllib.error.HTTPError as exc:
            warnings.warn(f"[ergast] season {year}: HTTP {exc.code} ({exc.reason})")
            return races
        except urllib.error.URLError as exc:
            warnings.warn(f"[ergast] season {year}: network error ({exc.reason})")
            return races
        mr = payload.get("MRData", {})
        table = mr.get("RaceTable", {})
        page = table.get("Races", []) or []
        races.extend(page)
        # Jolpica reports total in MRData.total (string).  Use it to decide
        # whether to keep paginating.
        try:
            total = int(mr.get("total", "0"))
        except (TypeError, ValueError):
            total = len(races)
        if len(races) >= total or not page:
            break
        offset += limit
        time.sleep(per_request_sleep_s)
    return races


def race_to_rows(race: dict, source: str = "ergast") -> list[HistoryRow]:
    """Convert one Jolpica race dict to ``HistoryRow``s.

    Schema keys we depend on:
    * ``season`` (str → int), ``round`` (str → int)
    * ``Results[]``: each has ``position`` (str → int) and ``Driver.code``
      (3-letter abbreviation; absent for some pre-1980 entries — fall back
      to driverId).
    * ``Results[i].grid`` (str → int): qualifying/starting position.  Used as
      ``predicted_position`` proxy.  ``"0"`` indicates pit-lane start in
      Ergast convention — treat as NULL.
    """
    try:
        season = int(race["season"])
        rnd = int(race["round"])
    except (KeyError, TypeError, ValueError):
        return []
    results = race.get("Results", []) or []
    out: list[HistoryRow] = []
    for entry in results:
        driver_block = entry.get("Driver", {}) or {}
        # Prefer 3-letter `code` (e.g. "VER"); fall back to driverId for
        # historical drivers who don't have one.
        code = driver_block.get("code") or driver_block.get("driverId")
        if not code:
            continue
        actual_pos = _safe_int(entry.get("position"))
        grid_pos = _safe_int(entry.get("grid"))
        # Grid 0 in Ergast convention is "pit-lane start"; treat as no signal.
        predicted_pos = grid_pos if grid_pos and grid_pos > 0 else None
        out.append(
            HistoryRow(
                season=season,
                round=rnd,
                driver=str(code).upper(),
                predicted_position=predicted_pos,
                actual_position=actual_pos,
                predicted_lap_time=None,
            )
        )
    return out


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def _insert_rows_with_source(
    conn: duckdb.DuckDBPyConnection,
    rows: Iterable[HistoryRow],
    source: str,
) -> None:
    """Insert HistoryRows tagged with a ``source`` value.

    Uses the same column order as ``backfill_history.insert_rows`` plus the
    new ``source`` column.  Caller is responsible for any prior-row deletion
    (handled by the orchestrator when ``--force`` is set).
    """
    payload = [
        (
            r.season,
            r.round,
            r.driver,
            r.predicted_position,
            r.actual_position,
            r.predicted_lap_time,
            source,
        )
        for r in rows
    ]
    if not payload:
        return
    conn.executemany(
        "INSERT INTO historical_predictions "
        "(season, round, driver, predicted_position, actual_position, "
        " predicted_lap_time, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        payload,
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def backfill_seasons(
    seasons: Iterable[int],
    db_path: Path | str = DEFAULT_DB_PATH,
    force: bool = False,
    show_progress: bool = True,
    user_agent: str = DEFAULT_USER_AGENT,
    per_request_sleep_s: float = DEFAULT_PER_REQUEST_SLEEP_S,
) -> dict:
    """Walk seasons, fetch Jolpica, write rows to DB.

    Idempotent: skips (season, round) pairs already present unless
    ``force=True``.  Returns run statistics for callers (tests, CLI).
    """
    seasons = sorted({int(s) for s in seasons})
    for s in seasons:
        if s < EARLIEST_F1_SEASON:
            raise ValueError(
                f"season {s} predates F1 (earliest = {EARLIEST_F1_SEASON})"
            )

    conn = connect(db_path)
    ensure_source_column(conn)

    rounds_written = 0
    rounds_skipped = 0
    rounds_failed = 0

    iterator: Iterable[int] = seasons
    if show_progress and len(seasons) > 1:
        iterator = tqdm(seasons, desc="Ergast backfill", unit="season")

    for season in iterator:
        try:
            races = fetch_season_results(
                season,
                user_agent=user_agent,
                per_request_sleep_s=per_request_sleep_s,
            )
        except Exception as exc:  # noqa: BLE001 — fall back to next season
            warnings.warn(f"[ergast] season {season}: fetch failed ({exc})")
            rounds_failed += 1
            continue

        if not races:
            warnings.warn(f"[ergast] season {season}: no races returned")
            rounds_failed += 1
            continue

        for race in races:
            rows = race_to_rows(race)
            if not rows:
                continue
            rnd = rows[0].round
            if round_already_present(conn, season, rnd):
                if not force:
                    rounds_skipped += 1
                    continue
                delete_round(conn, season, rnd)
            _insert_rows_with_source(conn, rows, source="ergast")
            rounds_written += 1
        time.sleep(per_request_sleep_s)

    conn.close()
    return {
        "rounds_written": rounds_written,
        "rounds_skipped": rounds_skipped,
        "rounds_failed": rounds_failed,
        "seasons_processed": len(seasons),
        "db_path": str(db_path),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_seasons(spec: str) -> list[int]:
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(chunk))
    return sorted(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill F1 historical results from the Jolpica API "
        "(1950→present, results-only Tier 2)."
    )
    parser.add_argument(
        "--seasons",
        type=str,
        required=True,
        help="Comma- or range-separated seasons, e.g. '1950-2025' or "
        "'2010,2011,2012' or '1990-1999,2005'.",
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
        help="Re-ingest seasons already present in the DB (default: skip).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress tqdm progress bar.",
    )
    parser.add_argument(
        "--per-request-sleep",
        type=float,
        default=DEFAULT_PER_REQUEST_SLEEP_S,
        help="Sleep between season fetches (seconds). Default 0.30.",
    )
    parser.add_argument(
        "--user-agent",
        type=str,
        default=DEFAULT_USER_AGENT,
        help="Override the User-Agent header sent to Jolpica.",
    )
    args = parser.parse_args(argv)

    seasons = _parse_seasons(args.seasons)
    if not seasons:
        print("No seasons specified.", file=sys.stderr)
        return 2

    print(
        f"Ergast backfill: seasons={seasons[0]}-{seasons[-1]} "
        f"(n={len(seasons)}) → {args.db} (force={args.force})",
        file=sys.stderr,
    )

    result = backfill_seasons(
        seasons=seasons,
        db_path=args.db,
        force=args.force,
        show_progress=not args.quiet,
        user_agent=args.user_agent,
        per_request_sleep_s=args.per_request_sleep,
    )

    print(
        f"\nDone. written={result['rounds_written']}  "
        f"skipped={result['rounds_skipped']}  "
        f"failed={result['rounds_failed']}  "
        f"seasons={result['seasons_processed']}",
        file=sys.stderr,
    )

    if result["rounds_written"] == 0 and result["rounds_skipped"] == 0:
        # Every season failed (network, schema, all 5xx).  Signal CI.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
