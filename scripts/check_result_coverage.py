#!/usr/bin/env python3
"""Audit published result coverage offline, independently of live no-work probes.

Exit 1 for overdue/unverifiable coverage; 2 for an unreadable dataset. Calendar
dates establish when coverage needs attention, never whether a race ran or its
official classification is ingestible. Allow the full UTC race day plus 48 hours
for source publication. generatedAt describes an export, not a source check.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = ("f2", "f3", "indycar")
GRACE = timedelta(days=3)  # midnight race day -> end of day + 48 hours


def audit(data: dict, now: datetime) -> dict:
    """Inspect every calendar entry, including holes before later imported rounds."""
    if now.tzinfo is None:
        raise ValueError("audit time must include a timezone")
    calendar = data["calendar"]
    if not isinstance(calendar, list) or not calendar:
        raise ValueError("calendar is missing or empty")
    imported, overdue, unknown = [], [], []
    seen = set()
    for entry in calendar:
        rnd = entry["round"]
        if not isinstance(rnd, int) or rnd < 1 or rnd in seen:
            raise ValueError("calendar round numbers must be positive and unique")
        seen.add(rnd)
        if entry.get("completed") is True:
            imported.append(rnd)
            continue
        value = entry.get("featureDate") or entry.get("raceDate")
        try:
            date = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            unknown.append(rnd)
            continue
        if now >= date + GRACE:
            overdue.append(rnd)
    return {
        "season": data["season"],
        "asOf": now.astimezone(timezone.utc).isoformat(),
        "exportedAt": data.get("generatedAt"),
        "importedRounds": sorted(imported),
        "totalRounds": len(calendar),
        "pastDueRounds": sorted(overdue),
        "unknownDateRounds": sorted(unknown),
        "sourceAvailability": "not checked",
        "status": "past-due" if overdue else "unknown" if unknown else "no-past-due-gaps",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("series", choices=SERIES)
    parser.add_argument("--data", type=Path, help="override published summary path for offline tests")
    parser.add_argument("--as-of", help="ISO timestamp with timezone; defaults to current UTC")
    args = parser.parse_args(argv)
    path = args.data or ROOT / f"projects/{args.series}-predictions/website/public/data/{args.series}.json"
    try:
        now = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
        report = audit(json.loads(path.read_text()), now)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"::error::Cannot establish {args.series} result coverage: {exc}")
        return 2
    print(json.dumps(report, indent=2))
    description = (
        f"{args.series.upper()} {report['season']}: {len(report['importedRounds'])}/"
        f"{report['totalRounds']} rounds imported; past-due rounds {report['pastDueRounds']}; "
        f"unknown dates {report['unknownDateRounds']}. Source availability not checked. "
        "An export timestamp or no-work probe does not establish source freshness."
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a") as stream:
            stream.write(f"### Published result coverage\n\n{description}\n")
    if report["pastDueRounds"] or report["unknownDateRounds"]:
        print(f"::error::{description}")
        return 1
    print(description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
