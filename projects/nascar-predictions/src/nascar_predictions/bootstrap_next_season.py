"""Bootstrap next season's announced-calendar file so rollover is hands-off.

NASCAR announces the next Cup calendar in late summer/autumn; until the
official calendar lands this module writes a *placeholder* announced calendar:
the active season's venues carried forward with the race dates shifted by
+364 days per year (same weekday), plus the current teams and roster flagged
``lineup_provisional``. The payload lands in
``data/announced_seasons/<year>.json``, which ``config.py`` loads once
``season_rollover.py --start`` activates the year — no code edits required.

When the real calendar is announced, install it with ``--from-file <json>``
(same schema, ``placeholder: false``) or edit the generated file in place; the
live refresh then self-corrects against the official race list (round
count + race_id verification) once cf.nascar.com serves the new season.

Safety / hands-off guarantees:
- Idempotent: a year already generated is skipped unless ``--force``.
- A generated calendar does NOT become the active season until the rollover's
  ``--auto`` gate fires (active season complete + next season's first race
  date passed) — see season_rollover.py.

Usage:
    python -m nascar_predictions.bootstrap_next_season               # active year + 1
    python -m nascar_predictions.bootstrap_next_season --year 2027 --force
    python -m nascar_predictions.bootstrap_next_season --from-file announced_2027.json
    python -m nascar_predictions.bootstrap_next_season --dry-run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANNOUNCED_DIR = PROJECT_ROOT / "data" / "announced_seasons"


def _shift_date(iso: str, delta: timedelta) -> str:
    """Shift a YYYY-MM-DD string by delta; empty/invalid dates pass through."""
    try:
        return (datetime.strptime(iso[:10], "%Y-%m-%d").date() + delta).isoformat()
    except Exception:
        return iso or ""


def build_placeholder(year: int) -> dict:
    """Carry the active season's calendar/teams/roster forward to <year>.

    +364 days per year keeps each race on the same weekday — close enough for
    a placeholder that only gates the rollover and seeds the new season's
    skeleton until the official calendar is announced. Race ids are NOT
    carried (they are season-specific); the first live refresh resolves them
    from the new season's race list.
    """
    delta = timedelta(days=364 * (year - config.SEASON))
    calendar = []
    for i, meta in sorted(config.CALENDAR_META.items()):
        calendar.append(
            {
                "round": i,
                "key": meta["key"],
                "track": meta["track"],
                "raceName": meta["raceName"],
                "trackType": meta["trackType"],
                "kind": meta["kind"],
                "stageLaps": list(meta.get("stageLaps") or []),
                "date": _shift_date(meta.get("date", ""), delta),
                "raceId": None,
            }
        )
    return {
        "season": year,
        "label": config.season_label(year),
        "source": f"placeholder carried forward from {config.SEASON}",
        "placeholder": True,
        "lineup_provisional": True,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "first_race_date": calendar[0]["date"] if calendar else None,
        "calendar": calendar,
        "teams": [{"name": t.name, "color": t.color} for t in config.TEAMS],
        "roster": [
            {"code": c, "name": n, "team": t, "make": m, "pace": p}
            for (c, n, t, m, p) in config._ROSTER
        ],
        "part_time_drivers": config.PART_TIME_DRIVERS,
    }


def _validate_announced(payload: dict, year: int) -> list[str]:
    problems = []
    if int(payload.get("season", 0)) != year:
        problems.append(f"payload season={payload.get('season')} != requested year {year}")
    cal = payload.get("calendar")
    if not isinstance(cal, list) or not cal:
        problems.append("calendar missing/empty")
    else:
        for i, e in enumerate(cal, start=1):
            for field in ("key", "track"):
                if not e.get(field):
                    problems.append(f"calendar[{i}] missing '{field}'")
    return problems


def bootstrap(
    year: int | None,
    *,
    force: bool = False,
    dry_run: bool = False,
    from_file: Path | None = None,
    announced_dir: Path = ANNOUNCED_DIR,
) -> int:
    if year is None:
        year = int(config.SEASON) + 1

    out_path = announced_dir / f"{year}.json"
    if out_path.exists() and not force:
        print(
            f"data/announced_seasons/{year}.json already exists — nothing to do "
            "(use --force to regenerate)."
        )
        return 0

    if from_file is not None:
        payload = json.loads(Path(from_file).read_text(encoding="utf-8"))
        payload.setdefault("placeholder", False)
    else:
        payload = build_placeholder(year)

    problems = _validate_announced(payload, year)
    if problems:
        for p in problems:
            print(f"  invalid announced calendar: {p}")
        return 1

    kind = "announced" if not payload.get("placeholder") else "placeholder"
    print(
        f"Bootstrapping season {year} ({kind}): "
        f"{len(payload['calendar'])} rounds, {len(payload.get('roster', []))} drivers "
        f"(provisional lineup), first race "
        f"{payload.get('first_race_date') or payload['calendar'][0].get('date')}."
    )
    if dry_run:
        print(f"   [dry-run] would write {out_path}")
        return 0

    announced_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {out_path} — season {year} will roll over automatically once "
        f"season {config.SEASON} completes and {year}'s first race date passes."
    )
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--year", type=int, default=None,
                    help="Season to bootstrap (default: active season + 1).")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate even if the announced file exists.")
    ap.add_argument("--from-file", type=Path, default=None,
                    help="Install a real announced calendar (same JSON schema).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be written without touching disk.")
    args = ap.parse_args()
    raise SystemExit(
        bootstrap(args.year, force=args.force, dry_run=args.dry_run, from_file=args.from_file)
    )


if __name__ == "__main__":
    main()
