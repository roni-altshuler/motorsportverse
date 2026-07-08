"""Season rollover — archive a completed F2 season and start the next one.

Ported from the F1 flagship's ``scripts/season_rollover.py`` and adapted to
F2's package conventions: the season lives in ``config.py`` (2026 literals +
announced-calendar overrides), results come from the committed snapshot
``data/official_<year>.json``, and the website data contract is produced by
``f2_predictions.export`` into ``website/public/data/``.

  --archive <year>   Snapshot the active season's website data into
                     website/public/data/seasons/<year>/ (browsable as a past
                     season) and refresh seasons.json.

  --start <year>     Make <year> the active season: require its announced
                     calendar (data/announced_seasons/<year>.json — written by
                     bootstrap_next_season.py), drop the data/active_season.json
                     marker config.py reads, clear the top-level round files
                     (the new season's export regenerates them), and refresh
                     seasons.json.

  --auto             If the active season is COMPLETE (the snapshot says every
                     calendar round has results) AND the announced next season
                     has BEGUN (its first race date has passed), archive the
                     active season and start the next one. Otherwise it only
                     refreshes seasons.json — safe to call from the F2 cron on
                     every run.

All steps support --dry-run.

Run:  python -m f2_predictions.season_rollover --auto [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime
from pathlib import Path

from . import config
from .export import DEFAULT_OUT, write_seasons_index

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = PROJECT_ROOT / "data"
ANNOUNCED_DIR = SNAPSHOT_DIR / "announced_seasons"

# Top-level website files that belong to the ACTIVE season and must be snapshotted.
SEASON_FILES = [
    "f2.json",
    "calibration_summary.json",
    "model_health.json",
    "promotion_status.json",
]
SEASON_DIRS = ["rounds", "probabilities", "forward_eval"]


def _load_announced(year: int, announced_dir: Path = ANNOUNCED_DIR) -> dict | None:
    path = announced_dir / f"{year}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(payload.get("season", 0)) != year or not payload.get("calendar"):
        return None
    return payload


def _first_race_date(announced: dict) -> date | None:
    """The announced season's opening race date (sprint of round 1)."""
    raw = announced.get("first_race_date")
    if not raw:
        cal = announced.get("calendar") or []
        raw = (cal[0].get("sprint") or cal[0].get("feature")) if cal else None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def season_complete(
    year: int, *, snapshot_dir: Path = SNAPSHOT_DIR, total_rounds: int | None = None
) -> bool:
    """True when the season snapshot says every calendar round has results."""
    snap_path = snapshot_dir / f"official_{year}.json"
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    completed = int(snap.get("completedRounds", 0))
    total = int(snap.get("totalRounds") or total_rounds or len(config.CALENDAR))
    return total > 0 and completed >= total


def archive(
    year: int,
    *,
    data_dir: Path = DEFAULT_OUT,
    snapshot_dir: Path = SNAPSHOT_DIR,
    current_season: int | None = None,
    dry_run: bool = False,
) -> Path:
    """Copy the active season's website data into <data_dir>/seasons/<year>/."""
    dest = data_dir / "seasons" / str(year)
    files = [f for f in SEASON_FILES if (data_dir / f).exists()]
    dirs = [d for d in SEASON_DIRS if (data_dir / d).is_dir()]
    snap = snapshot_dir / f"official_{year}.json"
    print(f"Archiving season {year} -> {dest}")
    if dry_run:
        print(f"   would copy files: {files}")
        print(f"   would copy dirs:  {dirs}")
        if snap.exists():
            print(f"   would copy snapshot: {snap.name}")
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(data_dir / f, dest / f)
    for d in dirs:
        shutil.copytree(data_dir / d, dest / d, dirs_exist_ok=True)
    # The canonical results snapshot travels into the archive too.
    if snap.exists():
        shutil.copy2(snap, dest / snap.name)
    write_seasons_index(data_dir, current=current_season)
    print(f"Season {year} archived ({len(list(dest.rglob('*')))} files).")
    return dest


def start(
    year: int,
    *,
    data_dir: Path = DEFAULT_OUT,
    snapshot_dir: Path = SNAPSHOT_DIR,
    announced_dir: Path | None = None,
    dry_run: bool = False,
) -> None:
    """Make <year> the active season (requires its announced calendar)."""
    announced_dir = announced_dir if announced_dir is not None else snapshot_dir / "announced_seasons"
    if year != config._DEFAULT_SEASON and _load_announced(year, announced_dir) is None:
        raise SystemExit(
            f"No announced calendar for {year} "
            f"({announced_dir / f'{year}.json'} missing or invalid). Run "
            f"`python -m f2_predictions.bootstrap_next_season --year {year}` first."
        )
    print(f"Starting season {year} as the active season")
    if dry_run:
        print("   would write data/active_season.json, clear round files, refresh seasons.json")
        return
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "active_season.json").write_text(
        json.dumps({"season": year}, indent=2) + "\n", encoding="utf-8"
    )
    # Clear the active round files (the new season's export regenerates them).
    for sub in ("rounds", "probabilities"):
        d = data_dir / sub
        if d.is_dir():
            for rf in d.glob("round_*.json"):
                rf.unlink()
    write_seasons_index(data_dir, current=year)
    print(
        f"Season {year} is now active. Run `python -m f2_predictions.refresh` (once a "
        "feed exists) and `python -m f2_predictions.export` to populate it."
    )


def auto(
    *,
    data_dir: Path = DEFAULT_OUT,
    snapshot_dir: Path = SNAPSHOT_DIR,
    announced_dir: Path | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> bool:
    """Roll over automatically once the active season finished AND the next began.

    Mirrors F1's ``--auto`` semantics: the finished season keeps serving as the
    live site through the off-season; the archive+start pair only fires when the
    announced next season's first race date has passed. Returns True iff a
    rollover happened.
    """
    announced_dir = announced_dir if announced_dir is not None else snapshot_dir / "announced_seasons"
    today = today or date.today()
    active = int(config.SEASON)
    nxt = active + 1
    announced = _load_announced(nxt, announced_dir)
    print(f"auto: active={active}, next announced={'yes' if announced else 'no'}")

    def _no_op(reason: str) -> bool:
        print(f"No rollover: {reason}")
        if not dry_run:
            write_seasons_index(data_dir, current=active)
        return False

    if not season_complete(active, snapshot_dir=snapshot_dir):
        return _no_op(f"season {active} is not complete yet.")
    if announced is None:
        return _no_op(
            f"season {active} is complete but data/announced_seasons/{nxt}.json is missing "
            f"— run `python -m f2_predictions.bootstrap_next_season`."
        )
    first = _first_race_date(announced)
    if first is None or first > today:
        return _no_op(f"season {nxt} has not begun yet (first race: {first}).")

    print(f"Season {active} complete and season {nxt} has begun — rolling over.")
    archive(active, data_dir=data_dir, snapshot_dir=snapshot_dir,
            current_season=active, dry_run=dry_run)
    start(nxt, data_dir=data_dir, snapshot_dir=snapshot_dir,
          announced_dir=announced_dir, dry_run=dry_run)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
