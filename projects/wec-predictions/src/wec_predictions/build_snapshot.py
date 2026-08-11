"""Build committed FIA WEC snapshots from the Al Kamel timing archive.

Walks the official Al Kamel results archive (``fiawec.alkamelsystems.com``) via
the shared :class:`motorsport_data.sources.alkamel.AlKamelClient` and writes one
canonical snapshot per season. Endurance is **multi-class** (Hypercar, LMP2,
LMGT3, and the GTE classes in older seasons), so unlike the single-class series
every round carries a *per-class* classification and the competitor is the **car
entry**, not an individual — endurance is won by the car (team + crew), and the
crew rotates less than the car number moves.

Snapshot shape (consumed by :mod:`wec_predictions.sources.snapshot`)::

    season / sport / classes[] / fullCalendar[] / completedRounds[] / totalRounds
    entries[]  = this season's cars: {code, number, class, team, vehicle,
                                      manufacturer, drivers[]}
    results{round: {CLASS: [{code, number, position, status, laps, points}]}}

The current season is written to ``data/official_<year>.json``; prior seasons to
``data/history/<year>.json`` (the offline training corpus). Competitor **codes**
are ``<CLASS_TAG>-<number>`` (e.g. ``HYP-15``, ``LMP2-43``, ``GT3-34``) — stable
within a season and, because top entries keep their number across years, a strong
cross-season identity that the model's entry Elo leans on.

Run (network, one-off / cron)::

    PYTHONPATH=src ../../.venv/bin/python -m wec_predictions.build_snapshot \
        --seasons 2021-2026

Downstream builds/tests never run this; they read the committed JSON.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from motorsport_data.sources.alkamel import AlKamelClient, ClassificationRow

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_HOST = "https://fiawec.alkamelsystems.com"
_CHAMP_HINT = "FIA WEC"

# Standard WEC per-class points (top 10). WEC has varied the exact table over the
# years (pole points, Le Mans weighting); this canonical table is used only to
# derive a *standings-order* signal for the championship view and the standings
# baseline — the model and its accuracy gate rank on finishing POSITIONS, which
# are rule-agnostic and always official.
_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

# Class → short stable tag used in competitor codes. Order = display priority
# (top class first). Names have shifted across eras; all map to a stable tag.
_CLASS_TAGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"hypercar", re.I), "HYP"),
    (re.compile(r"\blmp1\b", re.I), "LMP1"),
    (re.compile(r"\blmp2\b", re.I), "LMP2"),
    (re.compile(r"lmgt3|\bgt3\b", re.I), "GT3"),
    (re.compile(r"lmgte\s*pro|gte\s*pro", re.I), "GTEP"),
    (re.compile(r"lmgte\s*am|gte\s*am", re.I), "GTEA"),
    (re.compile(r"lmgte|\bgte\b", re.I), "GTE"),
]

# Known manufacturers, longest-first so "Aston Martin" beats "Aston".
_MANUFACTURERS = [
    "Aston Martin", "Mercedes-AMG", "Mercedes", "Alfa Romeo",
    "BMW", "Ferrari", "Toyota", "Porsche", "Cadillac", "Peugeot", "Alpine",
    "Genesis", "Lamborghini", "McLaren", "Lexus", "Corvette", "Chevrolet",
    "Ford", "Oreca", "Ligier", "Dallara", "Audi", "Nissan", "Glickenhaus",
    "Vanwall", "Isotta Fraschini", "Aston", "Gibson", "Multimatic",
]

# Circuit / event display metadata (country for the calendar cards). Keyed by a
# normalised event name; unknowns fall back to just the title-cased event name.
_VENUE_META: dict[str, dict[str, str]] = {
    "imola": {"place": "Imola", "country": "Italy"},
    "spa francorchamps": {"place": "Spa-Francorchamps", "country": "Belgium"},
    "le mans": {"place": "Le Mans", "country": "France"},
    "sao paulo": {"place": "São Paulo", "country": "Brazil"},
    "losail": {"place": "Losail", "country": "Qatar"},
    "circuit of the americas": {"place": "Austin", "country": "United States"},
    "fuji speedway": {"place": "Fuji", "country": "Japan"},
    "bahrain international circuit": {"place": "Sakhir", "country": "Bahrain"},
    "sebring": {"place": "Sebring", "country": "United States"},
    "autodromo do algarve": {"place": "Portimão", "country": "Portugal"},
    "autodromo nazionale di monza": {"place": "Monza", "country": "Italy"},
    "silverstone": {"place": "Silverstone", "country": "United Kingdom"},
    "nurburgring": {"place": "Nürburgring", "country": "Germany"},
    "autodromo hermanos rodriguez": {"place": "Mexico City", "country": "Mexico"},
    "shanghai international circuit": {"place": "Shanghai", "country": "China"},
    "paul ricard": {"place": "Paul Ricard", "country": "France"},
    "barcelona-catalunya": {"place": "Barcelona", "country": "Spain"},
    "interlagos": {"place": "São Paulo", "country": "Brazil"},
    "zhuhai international circuit": {"place": "Zhuhai", "country": "China"},
}

# Events that are tests/prologues, never scored — skip if they somehow parse.
_SKIP_EVENT = re.compile(r"prologue|test|\bthe prologue\b", re.I)

# Non-championship / exhibition classes (experimental hydrogen & Garage-56-style
# one-off entries) — never part of the class title fight, so excluded.
_SKIP_CLASS = re.compile(r"innovative|garage\s*56|hydrogen|hypercar\s*h2|mission\s*h24", re.I)


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
    key = re.sub(r"\s+\d+\s*hours?$", "", key)  # "BAHRAIN … 8 HOURS" → base
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
    events = [e for e in client.list_events(season_folder) if not _SKIP_EVENT.search(e.name)]

    results: dict[str, dict[str, list[dict]]] = {}
    completed: list[int] = []
    calendar: list[dict] = []
    entries: dict[str, dict] = {}  # code → entry meta (last seen wins)
    classes_seen: dict[str, int] = {}

    for ev in events:
        vmeta = _venue(ev.name)
        cal_row = {
            "round": ev.round_no,
            "event": ev.name.title(),
            "eventFolder": ev.event_folder,
            "place": vmeta["place"],
            "country": vmeta["country"],
            "venue": re.sub(r"[^a-z0-9]+", "-", ev.name.lower()).strip("-"),
        }
        rows = client.race_classification(ev)
        if not rows:
            calendar.append({**cal_row, "completed": False})
            continue
        calendar.append({**cal_row, "completed": True})
        completed.append(ev.round_no)

        # partition by class, rank within class by overall position
        per_class: dict[str, list[ClassificationRow]] = {}
        for r in rows:
            if _SKIP_CLASS.search(r.cls):
                continue
            per_class.setdefault(r.cls, []).append(r)

        round_block: dict[str, list[dict]] = {}
        for cls, crows in per_class.items():
            classes_seen[cls] = classes_seen.get(cls, 0) + 1
            # class finishing order: classified first by overall position, then
            # the rest (retired / not classified) preserving CSV order.
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
        results[str(ev.round_no)] = round_block

    # class display order: known priority first, then by frequency
    priority = ["HYPERCAR", "LMP1", "LMP2", "LMGT3", "LMGTE PRO", "LMGTE AM", "GTE"]
    ordered_classes = sorted(
        classes_seen,
        key=lambda c: (priority.index(c) if c in priority else 99, -classes_seen[c], c),
    )

    manufacturers = sorted({e["manufacturer"] for e in entries.values()})

    return {
        "sport": "FIA WEC",
        "season": year,
        "generatedFrom": "fiawec.alkamelsystems.com",
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
    ap.add_argument("--seasons", default="2021-2026", help="e.g. 2021-2026 or 2024,2025")
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
