#!/usr/bin/env python3
"""Season rollover — archive a completed season and start the next one.

The model layer is already multi-season (history.duckdb, models/registry/, the
``CALENDAR_<year>`` constant scanner). This script handles the *website data*
side so the same machinery serves future seasons automatically:

  --archive <year>   Snapshot the active season's website data into
                     website/public/data/seasons/<year>/ (browsable as a past
                     season) and refresh seasons.json.

  --start <year>     Make <year> the active season: validate CALENDAR_<year>
                     exists, write a fresh season.json + empty tracker/results,
                     and clear the top-level round files (the new season's
                     pipeline regenerates them). Refreshes seasons.json.

  --auto             If the active season is COMPLETE (its final calendar round
                     has actual results) and a newer CALENDAR_<year> exists,
                     archive the active season and start the newest one.

All steps support --dry-run. Designed to be safe to call from the race-weekend
cron: --auto is a no-op until a season genuinely finishes and a new calendar
has been added.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "website" / "public" / "data"
SEASONS_DIR = DATA_DIR / "seasons"

# Top-level website files that belong to the ACTIVE season and must be snapshotted.
_SEASON_FILES = [
    "season.json", "standings.json", "season_tracker.json",
    "gp_accuracy_report.json", "championship_forecast.json", "weather.json",
    "model_health.json", "promotion_status.json",
]
_SEASON_DIRS = ["rounds", "probabilities", "forward_eval", "visualizations"]


def _available_calendar_years() -> list[int]:
    from f1_prediction_utils import _available_season_years
    return _available_season_years("CALENDAR")


def _active_year() -> int:
    from f1_prediction_utils import get_season_year
    return int(get_season_year())


def _season_complete(year: int) -> bool:
    """True when every classifiable round of <year>'s calendar has a result."""
    from f1_prediction_utils import get_calendar
    cal = get_calendar(year)
    last_round = max(cal.keys())
    results_path = ROOT / f"season_results_{year}.json"
    if not results_path.exists():
        return False
    try:
        results = json.loads(results_path.read_text())
    except Exception:
        return False
    return str(last_round) in results and bool(results[str(last_round)])


def _refresh_index():
    import export_website_data as ew
    return ew._write_seasons_index()


def archive(year: int, dry_run: bool = False) -> None:
    dest = SEASONS_DIR / str(year)
    print(f"📦 Archiving season {year} → {dest.relative_to(ROOT)}")
    if dry_run:
        files = [f for f in _SEASON_FILES if (DATA_DIR / f).exists()]
        dirs = [d for d in _SEASON_DIRS if (DATA_DIR / d).is_dir()]
        print(f"   would copy files: {files}")
        print(f"   would copy dirs:  {dirs}")
        print(f"   would copy root: predicted_results_{year}.json, season_results_{year}.json")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for f in _SEASON_FILES:
        src = DATA_DIR / f
        if src.exists():
            shutil.copy2(src, dest / f)
    for d in _SEASON_DIRS:
        src = DATA_DIR / d
        if src.is_dir():
            shutil.copytree(src, dest / d, dirs_exist_ok=True)
    # Year-stamped canonical results (root) — copy into the archive too.
    for root_file in (f"predicted_results_{year}.json", f"season_results_{year}.json",
                      f"season_tracker_{year}.json"):
        src = ROOT / root_file
        if src.exists():
            shutil.copy2(src, dest / root_file)
    _refresh_index()
    print(f"✅ Season {year} archived ({len(list(dest.rglob('*')))} files).")


def start(year: int, dry_run: bool = False) -> None:
    if year not in _available_calendar_years():
        raise SystemExit(
            f"❌ No CALENDAR_{year} defined. Add the calendar constant in "
            f"f1_prediction_utils.py before starting season {year}.")
    print(f"🌱 Starting season {year} as the active season")
    if dry_run:
        print("   would write fresh season.json + empty tracker/results, clear rounds/")
        return
    os.environ["F1_SEASON_YEAR"] = str(year)
    # Fresh, empty per-season state.
    for stub in (f"predicted_results_{year}.json", f"season_results_{year}.json"):
        for base in (ROOT, DATA_DIR):
            (base / stub).write_text("{}\n")
    (ROOT / f"season_tracker_{year}.json").write_text(
        json.dumps({"rounds": {}, "accuracy": {}}, indent=2))
    # Clear the active round files (the new season regenerates them).
    rounds_dir = DATA_DIR / "rounds"
    if rounds_dir.is_dir():
        for rf in rounds_dir.glob("round_*.json"):
            rf.unlink()
    # Re-import with the new year so module globals pick it up, then write metadata.
    import importlib
    import f1_prediction_utils as fpu
    importlib.reload(fpu)
    import export_website_data as ew
    importlib.reload(ew)
    ew.export_season_metadata()
    print(f"✅ Season {year} is now active. Run the pipeline to populate rounds.")


def auto(dry_run: bool = False) -> None:
    active = _active_year()
    calendars = _available_calendar_years()
    newest = max(calendars) if calendars else active
    print(f"🔎 auto: active={active}, newest calendar={newest}, "
          f"active complete={_season_complete(active)}")
    if newest > active and _season_complete(active):
        print(f"➡️  Season {active} complete and {newest} calendar present — rolling over.")
        archive(active, dry_run=dry_run)
        start(newest, dry_run=dry_run)
    else:
        print("✅ No rollover needed (season ongoing or no newer calendar).")
        _refresh_index() if not dry_run else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=int, metavar="YEAR")
    ap.add_argument("--start", type=int, metavar="YEAR")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.archive:
        archive(args.archive, dry_run=args.dry_run)
    elif args.start:
        start(args.start, dry_run=args.dry_run)
    elif args.auto:
        auto(dry_run=args.dry_run)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
