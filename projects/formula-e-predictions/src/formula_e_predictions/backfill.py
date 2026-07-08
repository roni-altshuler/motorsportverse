"""Backfill FE history: the full Pulselive archive + predicted-vs-actual pairs.

Two jobs, one durable store (``motorsport_data.store.HistoryStore`` at
``data/history.duckdb``):

``--history`` (network, cheap to re-run)
    Pulls every points race of every FE season (2014-15 → present; seasons are
    keyed by ENDING year) into the history store as actual-result rows, and
    writes committed per-season JSON snapshots (``data/seasons/<year>.json``)
    for the recent seasons the model reads offline (the Elo seed window,
    ``config.ELO_FIRST_SEASON`` onward). Raw API responses are cached on disk
    (``data/api_cache/``) during the pull so reruns cost almost nothing.

default (offline, F3 parity)
    Re-runs the leakage-safe forecast for each completed round of the active
    season and upserts one predicted-vs-actual row per (round, driver) — the
    durable record the calibration layer and forward-eval consume. These rows
    overwrite the actual-only history rows for the same key with fuller ones.

Run:  python -m formula_e_predictions.backfill --history        # network pull
      python -m formula_e_predictions.backfill                  # offline pairs
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from motorsport_data.store import HistoryRow, HistoryStore

from . import config, pipeline
from .datasource import FEDataSource
from .sources.pulselive_source import (
    PulseliveClient,
    PulseliveFESource,
    points_races,
    season_of_championship,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "history.duckdb"
DEFAULT_CACHE = PROJECT_ROOT / "data" / "api_cache"
SEASONS_DIR = PROJECT_ROOT / "data" / "seasons"

# Cities whose FE round runs on a permanent (or semi-permanent) road course;
# everything else on the calendar is a street circuit. Drives the historical
# venue ``kind`` (the calibration stratum) for archived seasons.
CIRCUIT_CITIES = {
    "mexico city",
    "puebla",
    "valencia",
    "marrakesh",
    "portland",
    "misano",
    "shanghai",
    "madrid",
    "miami",
    "berlin",  # Tempelhof: airfield, kerbs-and-runway — closer to circuit than walls
}


def _slug(city: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (city or "round").lower()).strip("-")
    return s or "round"


def _venue_kind(city: str) -> str:
    return "circuit" if (city or "").strip().lower() in CIRCUIT_CITIES else "street"


# --------------------------------------------------------------------------- #
# --history: the full Pulselive archive
# --------------------------------------------------------------------------- #
def available_seasons(races: list[dict]) -> list[int]:
    """Every season (ending-year key) with at least one points race."""
    return sorted(
        {
            s
            for r in races
            if (s := season_of_championship(r.get("championship") or {})) is not None
        }
    )


def _season_snapshot(source: PulseliveFESource, year: int, races: list[dict]) -> dict:
    """Per-season snapshot (same shape as the active-season snapshot, minus
    standings/qualifying — the model needs calendar + results only)."""
    season_races = points_races(races, year)
    results: dict[str, dict] = {}
    calendar: list[dict] = []
    completed = 0
    for rnd, race in enumerate(season_races, start=1):
        city = race.get("city") or ""
        entry = {
            "round": rnd,
            "key": _slug(city),
            "name": city or (race.get("name") or f"Round {rnd}"),
            "country": race.get("country"),
            "kind": _venue_kind(city),
            "city": city,
            "date": race.get("date"),
            "completed": False,
            "raceId": race.get("id"),
        }
        if race.get("hasRaceResults"):
            rows = source.race_rows(year, rnd)
            if rows and any(r.get("position") for r in rows):
                results[str(rnd)] = {"race": rows, "raceId": race.get("id")}
                entry["completed"] = True
                completed += 1
        calendar.append(entry)
    return {
        "season": year,
        "source": "api.formula-e.pulselive.com",
        "completedRounds": completed,
        "totalRounds": len(season_races),
        "calendar": calendar,
        "results": results,
    }


def _history_rows(year: int, snapshot: dict) -> list[HistoryRow]:
    rows: list[HistoryRow] = []
    for rnd_str, block in snapshot.get("results", {}).items():
        for r in block.get("race", []):
            rows.append(
                HistoryRow(
                    sport=config.SPORT,
                    season=year,
                    round=int(rnd_str),
                    competitor=r["code"],
                    predicted_position=None,
                    actual_position=r.get("position"),
                    predicted_value=None,
                    source="pulselive",
                )
            )
    return rows


def backfill_history(
    db_path: Path = DEFAULT_DB,
    *,
    cache_dir: Path = DEFAULT_CACHE,
    seasons_dir: Path = SEASONS_DIR,
    snapshot_first_season: int | None = None,
    upto_season: int | None = None,
) -> dict:
    """Pull the full archive. Returns a coverage report dict."""
    client = PulseliveClient(cache_dir=cache_dir)
    source = PulseliveFESource(client=client)
    races = client.all_races()
    if races is None:
        raise RuntimeError("Pulselive race list unavailable — backfill aborted (no-op)")

    snapshot_first = snapshot_first_season or config.ELO_FIRST_SEASON
    last = upto_season or config.SEASON
    seasons = [s for s in available_seasons(races) if s <= last]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(db_path)
    report: dict = {"seasons": {}, "rows": 0, "snapshots": []}
    try:
        for year in seasons:
            snap = _season_snapshot(source, year, races)
            rows = _history_rows(year, snap)
            written = store.upsert(rows)
            report["rows"] += written
            report["seasons"][year] = {
                "races": snap["completedRounds"],
                "totalListed": snap["totalRounds"],
                "resultRows": len(rows),
            }
            # Commit offline season snapshots for the model's Elo/backtest
            # window (the ACTIVE season's snapshot is refresh.py's job).
            if snapshot_first <= year < config.SEASON:
                seasons_dir.mkdir(parents=True, exist_ok=True)
                out = seasons_dir / f"{year}.json"
                out.write_text(
                    json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                report["snapshots"].append(str(out))
            print(
                f"  {year}: {snap['completedRounds']}/{snap['totalRounds']} races, "
                f"{len(rows)} result rows"
            )
    finally:
        store.close()
    return report


# --------------------------------------------------------------------------- #
# default: predicted-vs-actual pairs for the active season (offline)
# --------------------------------------------------------------------------- #
def _rows_for_round(source: FEDataSource, year: int, rnd: int) -> list[HistoryRow]:
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
    source = FEDataSource()
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
        help="pull the FULL Pulselive archive (network) into the store + write "
        "per-season snapshots; default is the offline predicted-vs-actual pass",
    )
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = p.parse_args()
    if args.history:
        report = backfill_history(args.db, cache_dir=args.cache_dir)
        n_seasons = len(report["seasons"])
        n_races = sum(s["races"] for s in report["seasons"].values())
        print(
            f"backfill --history: {n_seasons} seasons, {n_races} races, "
            f"{report['rows']} result rows → {args.db}; "
            f"{len(report['snapshots'])} season snapshot(s) committed"
        )
        return 0
    written, provenance = backfill(args.season, args.db)
    print(f"backfill: wrote {written} rows to {args.db} · provenance={provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
