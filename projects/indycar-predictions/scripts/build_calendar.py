"""Emit data/calendar_{year}.json — the full season calendar with dates,
venues and track types, and a completed flag per round.

Usage: python scripts/build_calendar.py --year 2026
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse as P  # noqa: E402
from curate_season import _iso_date, _venue_key  # noqa: E402
from wiki import wikitext  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    year = args.year

    w = wikitext(f"{year} IndyCar Series", refresh=args.refresh)
    schedule = P.parse_schedule(w)
    today = date.today().isoformat()

    cal = []
    for r in schedule:
        iso = _iso_date(r.get("date_md"), year)
        cal.append(
            {
                "round": r["round"],
                "name": r.get("race_name"),
                "venue": r.get("venue"),
                "venue_key": _venue_key(r.get("venue")),
                "date": iso,
                "track_type": r.get("track_type"),
                "completed": bool(iso and iso < today),
            }
        )
    n_done = sum(1 for c in cal if c["completed"])
    out = {
        "season": year,
        "source": "en.wikipedia.org (CC BY-SA)",
        "generated": today,
        "total_rounds": len(cal),
        "completed_rounds": n_done,
        "remaining_rounds": len(cal) - n_done,
        "calendar": cal,
    }
    (DATA / f"calendar_{year}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"calendar_{year}.json: {len(cal)} rounds, {n_done} completed, "
          f"{len(cal) - n_done} remaining")
    for c in cal:
        mark = "x" if c["completed"] else " "
        print(f"  [{mark}] R{c['round']:>2} {c['date']}  {c['track_type']:<6} {c['venue']}")


if __name__ == "__main__":
    main()
