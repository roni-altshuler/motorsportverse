"""Build committed IMSA WeatherTech snapshots from the Al Kamel timing archive.

Walks the official IMSA results archive (``imsa.results.alkamelcloud.com``) via
the shared :class:`motorsport_data.sources.alkamel.AlKamelClient` and writes one
canonical snapshot per season. IMSA is **multi-class** (GTP/DPi, LMP2, GTD PRO,
GTD, plus LMP3 in the 2022-2023 era), so unlike a single-class series every round
carries a *per-class* classification and the competitor is the **car entry**, not
an individual — endurance is won by the car (team + crew).

**Round renumbering.** IMSA's event folders interleave support series (MX-5 Cup,
VP Racing / SportsCar Challenge, Michelin Pilot Challenge, Porsche Carrera Cup,
tests, the ROAR-before-the-24 shakedown), so the folder index is *not* the
WeatherTech round number. We therefore (1) skip test/ROAR/support-only events by
name and (2) keep only events that actually yield a non-empty WeatherTech race
classification (a support-only weekend has no ``01_IMSA WeatherTech`` folder, so
its classification is empty under the champ hint), then (3) assign sequential
round numbers ``1..N`` in calendar order.

Snapshot shape (consumed by :mod:`imsa_predictions.sources.snapshot`)::

    season / sport / classes[] / fullCalendar[] / completedRounds[] / totalRounds
    entries[]  = this season's cars: {code, number, class, team, vehicle,
                                      manufacturer, drivers[]}
    results{round: {CLASS: [{code, number, position, status, laps, points}]}}

The current season is written to ``data/official_<year>.json``; prior seasons to
``data/history/<year>.json`` (the offline training corpus). Competitor **codes**
are ``<CLASS_TAG>-<number>`` (e.g. ``GTP-7``, ``LMP2-22``, ``GTDP-65``) — stable
within a season and, because top entries keep their number across years, a strong
cross-season identity that the model's entry Elo leans on.

Run (network, one-off / cron)::

    PYTHONPATH=src ../../.venv/bin/python -m imsa_predictions.build_snapshot \
        --seasons 2022-2026 --current 2026

Downstream builds/tests never run this; they read the committed JSON.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from motorsport_data.sources.alkamel import AlKamelClient, ClassificationRow

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_HOST = "https://imsa.results.alkamelcloud.com"
_CHAMP_HINT = "IMSA WeatherTech"
SPORT = "IMSA WeatherTech SportsCar Championship"

# Approximate IMSA per-class points (P1=350 sliding to a floor). Used only to
# derive a *standings-order* signal for the championship view and the standings
# baseline — the model and its accuracy gate rank on finishing POSITIONS, which
# are rule-agnostic and always official.
def _points_table(n: int = 45) -> dict[int, int]:
    t = {1: 350, 2: 320, 3: 300, 4: 280, 5: 260}
    for p in range(6, n + 1):
        t[p] = max(25, 250 - (p - 6) * 10)
    return t


_POINTS = _points_table()

# Class → short stable tag used in competitor codes. Order = check priority; the
# GTD-PRO pattern MUST be tested before the bare GTD one ("GTD" is a substring).
_CLASS_TAGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bgtp\b", re.I), "GTP"),
    (re.compile(r"\bdpi\b", re.I), "DPI"),
    (re.compile(r"gtd\s*pro|gtdpro", re.I), "GTDP"),
    (re.compile(r"\blmp2\b", re.I), "LMP2"),
    (re.compile(r"\blmp3\b", re.I), "LMP3"),
    (re.compile(r"\bgtd\b", re.I), "GTD"),
]

# Known manufacturers, longest-first so "Aston Martin" beats "Aston". Matched
# against the ``VEHICLE`` column ("Porsche 963", "Chevrolet Corvette Z06 GT3.R").
_MANUFACTURERS = [
    "Aston Martin", "Mercedes-AMG", "Mercedes", "BMW", "Ferrari", "Porsche",
    "Cadillac", "Acura", "Lamborghini", "McLaren", "Lexus", "Chevrolet", "Corvette",
    "Ford", "Oreca", "Ligier", "Duqueine", "Riley", "Multimatic", "Gibson", "Dallara",
]

# Circuit / event display metadata (place + country for the calendar cards). Keyed
# by a normalised event name; unknowns fall back to the title-cased event name.
_VENUE_META: dict[str, dict[str, str]] = {
    "daytona international speedway": {"place": "Daytona Beach", "country": "United States"},
    "sebring international raceway": {"place": "Sebring", "country": "United States"},
    "long beach street circuit": {"place": "Long Beach", "country": "United States"},
    "weathertech raceway laguna seca": {"place": "Monterey", "country": "United States"},
    "detroit street course": {"place": "Detroit", "country": "United States"},
    "belle isle street course": {"place": "Detroit", "country": "United States"},
    "mid-ohio sports car course": {"place": "Lexington", "country": "United States"},
    "watkins glen international": {"place": "Watkins Glen", "country": "United States"},
    "canadian tire motorsport park": {"place": "Bowmanville", "country": "Canada"},
    "lime rock park": {"place": "Lakeville", "country": "United States"},
    "road america": {"place": "Elkhart Lake", "country": "United States"},
    "virginia international raceway": {"place": "Alton", "country": "United States"},
    "indianapolis motor speedway rc": {"place": "Indianapolis", "country": "United States"},
    "tire rack.com battle on the bricks": {"place": "Indianapolis", "country": "United States"},
    "road atlanta": {"place": "Braselton", "country": "United States"},
    "miami grand prix": {"place": "Miami", "country": "United States"},
    "michelin raceway road atlanta": {"place": "Braselton", "country": "United States"},
}

# Events that are tests / shakedowns / support-series-only weekends — skip by name
# even if they somehow parse (the 2022 "ROAR Before the 24" shakedown, notably,
# produces a full classification but is NOT a points round).
_SKIP_EVENT = re.compile(
    r"\btest\b|\broar\b|prologue|shakedown|"
    r"\(mx-?5\)|mx-?5\s*cup|"
    r"\(vprc\)|\(aec\)|\(pccna\)|\bpccna\b|\(mc\)|\(lst\)|\blst\b|\(pc\)",
    re.I,
)

# Michelin Endurance Cup rounds (the long-distance classics) — a display flag.
_ENDURANCE_CUP = re.compile(r"daytona|sebring|watkins\s*glen|road\s*atlanta|battle\s*on\s*the\s*bricks", re.I)

# Non-championship classes — none expected under the WeatherTech champ hint, but
# guard against a blank/unknown class leaking a competitor code.
_SKIP_CLASS = re.compile(r"^\s*$|unknown", re.I)


def class_tag(cls: str) -> str:
    for pat, tag in _CLASS_TAGS:
        if pat.search(cls):
            return tag
    # unknown class: compact alnum tag
    return re.sub(r"[^A-Z0-9]", "", cls.upper())[:4] or "UNK"


def manufacturer_of(vehicle: str) -> str:
    for m in _MANUFACTURERS:
        if vehicle.lower().startswith(m.lower()) or f" {m.lower()}" in f" {vehicle.lower()}":
            return "Mercedes-AMG" if m in ("Mercedes",) else m
    return (vehicle.split() or ["Unknown"])[0]


def _venue(name: str) -> dict[str, str]:
    key = re.sub(r"\s+", " ", name).strip().lower()
    if key in _VENUE_META:
        return _VENUE_META[key]
    return {"place": name.title(), "country": ""}


def code_of(row: ClassificationRow) -> str:
    return f"{class_tag(row.cls)}-{row.number}"


def _points(position: int | None, classified: bool) -> float:
    if not classified or position is None:
        return 0.0
    return float(_POINTS.get(position, 0))


def build_season(client: AlKamelClient, season_folder: str, year: int) -> dict:
    # (1) keep only real WeatherTech races: not a test/support event by name, AND
    #     yielding a non-empty race classification (support-only weekends return
    #     empty under the champ hint). Preserve calendar (folder) order.
    kept: list[tuple[object, list[ClassificationRow]]] = []
    for ev in client.list_events(season_folder):
        if _SKIP_EVENT.search(ev.name):
            continue
        rows = client.race_classification(ev)
        if not rows:
            continue
        kept.append((ev, rows))

    results: dict[str, dict[str, list[dict]]] = {}
    completed: list[int] = []
    calendar: list[dict] = []
    entries: dict[str, dict] = {}  # code → entry meta (last seen wins)
    classes_seen: dict[str, int] = {}

    # (2) assign sequential WeatherTech round numbers 1..N in calendar order.
    for round_no, (ev, rows) in enumerate(kept, start=1):
        vmeta = _venue(ev.name)
        calendar.append({
            "round": round_no,
            "event": ev.name.title(),
            "eventFolder": ev.event_folder,
            "place": vmeta["place"],
            "country": vmeta["country"],
            "venue": re.sub(r"[^a-z0-9]+", "-", ev.name.lower()).strip("-"),
            "isEnduranceCup": bool(_ENDURANCE_CUP.search(ev.name)),
            "completed": True,
        })
        completed.append(round_no)

        # partition by class, rank within class by overall position
        per_class: dict[str, list[ClassificationRow]] = {}
        for r in rows:
            if _SKIP_CLASS.search(r.cls):
                continue
            per_class.setdefault(r.cls, []).append(r)

        round_block: dict[str, list[dict]] = {}
        for cls, crows in per_class.items():
            classes_seen[cls] = classes_seen.get(cls, 0) + 1
            classified = sorted((r for r in crows if r.classified), key=lambda r: r.position)
            others = [r for r in crows if not r.classified]
            out_rows: list[dict] = []
            for cls_pos, r in enumerate(classified, start=1):
                code = code_of(r)
                out_rows.append({
                    "code": code,
                    "number": r.number,
                    "position": cls_pos,          # position WITHIN class
                    "overall": r.position,        # overall race position
                    "status": r.status,
                    "laps": r.laps,
                    "points": _points(cls_pos, True),
                })
                entries[code] = {
                    "code": code, "number": r.number, "class": cls,
                    "classTag": class_tag(cls), "team": r.team, "vehicle": r.vehicle,
                    "manufacturer": manufacturer_of(r.vehicle), "drivers": list(r.drivers),
                }
            for r in others:
                code = code_of(r)
                out_rows.append({
                    "code": code, "number": r.number, "position": None,
                    "overall": None, "status": r.status, "laps": r.laps, "points": 0.0,
                })
                entries.setdefault(code, {
                    "code": code, "number": r.number, "class": cls,
                    "classTag": class_tag(cls), "team": r.team, "vehicle": r.vehicle,
                    "manufacturer": manufacturer_of(r.vehicle), "drivers": list(r.drivers),
                })
            round_block[cls] = out_rows
        results[str(round_no)] = round_block

    # class display order: known priority first, then by frequency
    priority = ["GTP", "DPI", "LMP2", "LMP3", "GTDPRO", "GTD"]
    ordered_classes = sorted(
        classes_seen,
        key=lambda c: (priority.index(c) if c in priority else 99, -classes_seen[c], c),
    )

    manufacturers = sorted({e["manufacturer"] for e in entries.values()})

    return {
        "sport": SPORT,
        "season": year,
        "generatedFrom": "imsa.results.alkamelcloud.com",
        "seasonFolder": season_folder,
        "classes": ordered_classes,
        "fullCalendar": calendar,
        "completedRounds": sorted(completed),
        "totalRounds": len(calendar),
        "manufacturers": manufacturers,
        "entries": sorted(entries.values(), key=lambda e: (e["classTag"], _num_key(e["number"]))),
        "results": results,
    }


def _num_key(n: str) -> tuple[int, str]:
    m = re.match(r"\d+", n)
    return (int(m.group()) if m else 9999, n)


def _parse_seasons(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", default="2022-2026", help="e.g. 2022-2026 or 2024,2025")
    ap.add_argument("--current", type=int, default=2026,
                    help="season written to official_<year>.json")
    ap.add_argument("--cache", default=str(_DATA_DIR / ".http_cache"),
                    help="disk cache dir for the Al Kamel archive (gitignored)")
    args = ap.parse_args()

    client = AlKamelClient(_HOST, _CHAMP_HINT, Path(args.cache))
    years = _parse_seasons(args.seasons)
    folder_for = {y: sf for sf, y in client.list_seasons()}

    (_DATA_DIR / "history").mkdir(parents=True, exist_ok=True)
    for y in years:
        sf = folder_for.get(y)
        if not sf:
            print(f"  ! {y}: no season folder in archive, skipping")
            continue
        snap = build_season(client, sf, y)
        path = _DATA_DIR / (f"official_{y}.json" if y == args.current
                            else f"history/{y}.json")
        path.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  {y}: {len(snap['completedRounds'])}/{snap['totalRounds']} rounds, "
              f"{len(snap['entries'])} entries, classes={snap['classes']} "
              f"-> {path.relative_to(_DATA_DIR.parent)}")

    # active-season marker (drives config season resolution)
    (_DATA_DIR / "active_season.json").write_text(
        json.dumps({"season": args.current}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
