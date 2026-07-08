"""Backfill NASCAR history: the cacher archive + predicted-vs-actual pairs.

Two jobs, one durable store (``motorsport_data.store.HistoryStore`` at
``data/history.duckdb``):

``--history`` (network, cheap to re-run)
    Pulls every Cup points race of every season from
    ``config.HISTORY_FIRST_SEASON`` (2017, the stage/playoff era — the playoff
    backtest's window) through the active season into the history store as
    actual-result rows, and writes committed per-season JSON snapshots
    (``data/seasons/<year>.json``) the model reads offline (Elo seed, the
    historical backtest AND the elimination-format playoff backtest). Raw API
    responses are cached on disk (``data/api_cache/``, gitignored) during the
    pull so reruns cost almost nothing. Respects the ~1 req/s throttle.

default (offline, family parity)
    Re-runs the leakage-safe forecast for each completed round of the active
    season and upserts one predicted-vs-actual row per (round, driver) — the
    durable record the calibration layer and forward-eval consume. These rows
    overwrite the actual-only history rows for the same key with fuller ones.

Run:  python -m nascar_predictions.backfill --history        # network pull
      python -m nascar_predictions.backfill                  # offline pairs
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

from motorsport_data.store import HistoryRow, HistoryStore

from . import config, pipeline
from .datasource import NascarDataSource
from .sources.nascar_feed_source import NascarCacherClient, NascarFeedSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "history.duckdb"
DEFAULT_CACHE = PROJECT_ROOT / "data" / "api_cache"
SEASONS_DIR = PROJECT_ROOT / "data" / "seasons"


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "round").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "round"


# --------------------------------------------------------------------------- #
# --history: the full cacher archive
# --------------------------------------------------------------------------- #
def _season_snapshot(source: NascarFeedSource, year: int) -> dict:
    """Per-season snapshot (same shape as the active-season snapshot, minus
    standings/qualifying/entries — the model and the playoff backtest need
    calendar + results + stages)."""
    races = source.season_races(year) or []
    results: dict[str, dict] = {}
    calendar: list[dict] = []
    completed = 0
    for rnd, race in enumerate(races, start=1):
        track = race.get("track_name") or ""
        entry = {
            "round": rnd,
            "key": _slug(track),
            "track": track,
            "raceName": race.get("race_name") or f"Round {rnd}",
            "country": "United States",
            "trackType": config.track_type_of(track, year),
            "kind": "street"
            if "street" in track.lower()
            else ("circuit" if config.track_type_of(track, year) == "road" else "oval"),
            "date": str(race.get("race_date") or "")[:10],
            "stageLaps": [
                int(race.get("stage_1_laps") or 0),
                int(race.get("stage_2_laps") or 0),
                int(race.get("stage_3_laps") or 0),
            ],
            "completed": False,
            "raceId": race.get("race_id"),
        }
        rows = source.race_rows(year, rnd)
        if rows and any(r.get("position") for r in rows):
            block: dict = {"race": rows, "raceId": race.get("race_id")}
            stages = source.stage_results(year, rnd)
            if stages:
                block["stages"] = stages
            results[str(rnd)] = block
            entry["completed"] = True
            completed += 1
        calendar.append(entry)
    return {
        "season": year,
        "source": "cf.nascar.com",
        "series": config.CUP_SERIES_ID,
        "completedRounds": completed,
        "totalRounds": len(races),
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
                    source="nascar-feed",
                )
            )
    return rows


def backfill_history(
    db_path: Path = DEFAULT_DB,
    *,
    cache_dir: Path = DEFAULT_CACHE,
    seasons_dir: Path = SEASONS_DIR,
    first_season: int | None = None,
    upto_season: int | None = None,
) -> dict:
    """Pull the cacher archive. Returns a coverage report dict."""
    client = NascarCacherClient(cache_dir=cache_dir)
    source = NascarFeedSource(client=client)

    first = first_season or config.HISTORY_FIRST_SEASON
    last = upto_season or config.SEASON

    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(db_path)
    report: dict = {"seasons": {}, "rows": 0, "snapshots": []}
    try:
        for year in range(first, last + 1):
            if source.season_races(year) is None:
                print(f"  {year}: race list unavailable — skipped")
                continue
            snap = _season_snapshot(source, year)
            rows = _history_rows(year, snap)
            written = store.upsert(rows)
            report["rows"] += written
            n_stage_rounds = sum(
                1 for b in snap["results"].values() if b.get("stages")
            )
            report["seasons"][year] = {
                "races": snap["completedRounds"],
                "totalListed": snap["totalRounds"],
                "resultRows": len(rows),
                "roundsWithStages": n_stage_rounds,
            }
            # Commit offline season snapshots for past seasons (the ACTIVE
            # season's snapshot is refresh.py's job).
            if year < config.SEASON:
                seasons_dir.mkdir(parents=True, exist_ok=True)
                out = seasons_dir / f"{year}.json"
                out.write_text(
                    json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
                )
                report["snapshots"].append(str(out))
            print(
                f"  {year}: {snap['completedRounds']}/{snap['totalRounds']} races, "
                f"{len(rows)} result rows, {n_stage_rounds} rounds with stage data"
            )
    finally:
        store.close()
    return report


# --------------------------------------------------------------------------- #
# default: predicted-vs-actual pairs for the active season (offline)
# --------------------------------------------------------------------------- #
def _rows_for_round(source: NascarDataSource, year: int, rnd: int) -> list[HistoryRow]:
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
    source = NascarDataSource()
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
        help="pull the FULL cacher archive (network) into the store + write "
        "per-season snapshots; default is the offline predicted-vs-actual pass",
    )
    p.add_argument("--first-season", type=int, default=None)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = p.parse_args()
    if args.history:
        report = backfill_history(
            args.db, cache_dir=args.cache_dir, first_season=args.first_season
        )
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
