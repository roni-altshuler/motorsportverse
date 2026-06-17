"""Backfill predicted-vs-actual pairs into the shared HistoryStore.

For each completed round, re-runs the leakage-safe forecast and pairs it with the
actual classification from the active source, writing one row per (race, driver)
into ``motorsport_data.store.HistoryStore`` (DuckDB). This is the durable record
the calibration layer and forward-eval consume in Phase 2.

The store's primary key has no race-index column, so the sprint is stored under a
sentinel round offset (``round + SPRINT_ROUND_OFFSET``) to avoid colliding with
the feature race of the same weekend. Each row carries its ``source`` provenance
(synthetic / fastf1 / official) so the calibration gate counts only real rounds.

Run:  F2_USE_LIVE_RESULTS=1 python -m f2_predictions.backfill --season 2026 [--db <path>]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from motorsport_data.store import HistoryRow, HistoryStore

from . import config, model, pipeline
from .datasource import F2DataSource

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "history.duckdb"

# Sprint rows live at round + this offset so they don't collide with the feature
# race on the store's (sport, season, round, competitor) primary key.
SPRINT_ROUND_OFFSET = 50


def _rows_for_round(source: F2DataSource, year: int, rnd: int) -> list[HistoryRow]:
    fc = pipeline.forecast_round(source, year, rnd)
    races = (
        (fc.feature, model.FEATURE, 1, rnd),
        (fc.sprint, model.SPRINT, 0, rnd + SPRINT_ROUND_OFFSET),
    )
    rows: list[HistoryRow] = []
    for race, race_type, race_index, stored_round in races:
        actual = {r.competitor: r.position for r in source.race_results_for_round(year, rnd)[race_type]}
        predicted = {code: i for i, code in enumerate(race.order, start=1)}
        prov = source.provenance(year, rnd, race_index)
        for d in config.DRIVERS:
            code = d["code"]
            rows.append(
                HistoryRow(
                    sport=config.SPORT,
                    season=year,
                    round=stored_round,
                    competitor=code,
                    predicted_position=predicted.get(code),
                    actual_position=actual.get(code),
                    predicted_value=race.score.get(code),
                    source=prov,
                )
            )
    return rows


def backfill(year: int, db_path: Path) -> tuple[int, dict[str, int]]:
    """Write predicted-vs-actual rows for all completed rounds. Returns
    (rows_written, provenance_counts)."""
    source = F2DataSource()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(db_path)
    written = 0
    provenance: dict[str, int] = {}
    try:
        for rnd in range(1, config.COMPLETED_ROUNDS + 1):
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
    args = p.parse_args()
    written, provenance = backfill(args.season, args.db)
    print(f"backfill: wrote {written} rows to {args.db} · provenance={provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
