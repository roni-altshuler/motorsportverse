"""Backfill IndyCar history: the committed archive + predicted-vs-actual pairs.

Two jobs, one durable store (``motorsport_data.store.HistoryStore`` at
``data/history.duckdb``) — and, snapshot-primary as everything here, **neither
needs the network**: the committed ``data/history_<year>.json`` files ARE the
archive.

``--history`` (offline!)
    Loads every curated season (``config.HISTORY_FIRST_SEASON`` = 2012 through
    the active season) from the committed history files into the history store
    as actual-result rows. No API, no scraping — the files were curated and
    verified once (data/CURATION_REPORT.md) and are the source of truth.

default (offline, family parity)
    Re-runs the leakage-safe forecast for each completed round of the active
    season and upserts one predicted-vs-actual row per (round, driver) — the
    durable record the calibration layer and forward-eval consume. These rows
    overwrite the actual-only history rows for the same key with fuller ones.

Run:  python -m indycar_predictions.backfill --history      # offline archive load
      python -m indycar_predictions.backfill                # offline pairs
"""
from __future__ import annotations

import argparse
from pathlib import Path

from motorsport_data.store import HistoryRow, HistoryStore

from . import config, pipeline
from .datasource import IndycarDataSource
from .sources.snapshot import SnapshotIndycarSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "history.duckdb"


# --------------------------------------------------------------------------- #
# --history: the committed archive → the store (no network)
# --------------------------------------------------------------------------- #
def _history_rows(source: SnapshotIndycarSource, year: int) -> list[HistoryRow]:
    rows: list[HistoryRow] = []
    for rnd in source.completed_rounds(year):
        for r in source.race_rows(year, rnd) or []:
            rows.append(
                HistoryRow(
                    sport=config.SPORT,
                    season=year,
                    round=rnd,
                    competitor=r["code"],
                    predicted_position=None,
                    actual_position=r.get("position"),
                    predicted_value=None,
                    source="snapshot",
                )
            )
    return rows


def backfill_history(
    db_path: Path = DEFAULT_DB,
    *,
    first_season: int | None = None,
    upto_season: int | None = None,
) -> dict:
    """Load the committed history files into the store. Returns a coverage
    report dict. Fully offline — the curated files are canonical."""
    source = SnapshotIndycarSource()
    first = first_season or config.HISTORY_FIRST_SEASON
    last = upto_season or config.SEASON

    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(db_path)
    report: dict = {"seasons": {}, "rows": 0}
    try:
        for year in range(first, last + 1):
            rounds = source.completed_rounds(year)
            if not rounds:
                print(f"  {year}: no committed history file — skipped")
                continue
            rows = _history_rows(source, year)
            written = store.upsert(rows)
            report["rows"] += written
            report["seasons"][year] = {"rounds": len(rounds), "resultRows": len(rows)}
            print(f"  {year}: {len(rounds)} rounds, {len(rows)} result rows")
    finally:
        store.close()
    return report


# --------------------------------------------------------------------------- #
# default: predicted-vs-actual pairs for the active season (offline)
# --------------------------------------------------------------------------- #
def _rows_for_round(source: IndycarDataSource, year: int, rnd: int) -> list[HistoryRow]:
    fc = pipeline.forecast_round(source, year, rnd)
    actual = {r.competitor: r.position for r in source.results(year, rnd)}
    predicted = {code: i for i, code in enumerate(fc.race.order, start=1)}
    prov = source.provenance(year, rnd)
    rows: list[HistoryRow] = []
    for code in fc.race.score:
        rows.append(
            HistoryRow(
                sport=config.SPORT,
                season=year,
                round=rnd,
                competitor=code,
                predicted_position=predicted.get(code),
                actual_position=actual.get(code),
                predicted_value=fc.race.score.get(code),
                source=prov,
            )
        )
    return rows


def backfill(year: int, db_path: Path) -> tuple[int, dict[str, int]]:
    """Write predicted-vs-actual rows for all completed rounds. Returns
    (rows_written, provenance_counts)."""
    source = IndycarDataSource()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(db_path)
    written = 0
    provenance: dict[str, int] = {}
    try:
        for rnd in source.completed_rounds(year):
            rows = _rows_for_round(source, year, rnd)
            written += store.upsert(rows)
            for r in rows:
                provenance[r.source or "unknown"] = provenance.get(r.source or "unknown", 0) + 1
    finally:
        store.close()
    return written, provenance


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument(
        "--history",
        action="store_true",
        help="load the FULL committed archive (offline — the curated files are "
        "canonical) into the store; default is the predicted-vs-actual pass",
    )
    p.add_argument("--first-season", type=int, default=None)
    args = p.parse_args()
    if args.history:
        report = backfill_history(args.db, first_season=args.first_season)
        n_seasons = len(report["seasons"])
        n_rounds = sum(s["rounds"] for s in report["seasons"].values())
        print(
            f"backfill --history: {n_seasons} seasons, {n_rounds} rounds, "
            f"{report['rows']} result rows → {args.db} (offline, from the "
            "committed history files)"
        )
        return 0
    written, provenance = backfill(args.season, args.db)
    print(f"backfill: wrote {written} rows to {args.db} · provenance={provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
