"""Build committed MotoGP snapshots from the official results API.

Walks the pulselive API for the premier MotoGP class and writes one canonical
snapshot per season, in the exact shape the golden-template snapshot source
consumes (``season / calendar / results{round:{sprint,feature}} / qualifying /
driverStandings / teamStandings / riders / manufacturers``). The current season
is written to ``data/official_<year>.json``; prior seasons to
``data/history/<year>.json`` (the offline training corpus).

Rider **codes** are assigned once, globally, deterministically (surname TLA with
first-initial disambiguation on collision) so a rider keeps the same code across
every season and every downstream artifact.

Run (network, one-off / cron):

    PYTHONPATH=src ../../.venv/bin/python -m motogp_predictions.build_snapshot \
        --seasons 2021-2026

Downstream builds/tests never run this; they read the committed JSON.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from .sources.pulselive_source import MotoGPApi, _pick_sessions, rider_surname

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# MotoGP Grand Prix (25→1) and Sprint (12→1) points tables (2023+ sprint format).
_GP_POINTS = {1: 25, 2: 20, 3: 16, 4: 13, 5: 11, 6: 10, 7: 9, 8: 8, 9: 7,
              10: 6, 11: 5, 12: 4, 13: 3, 14: 2, 15: 1}
_SPR_POINTS = {1: 12, 2: 9, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1}


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


# --------------------------------------------------------------------------- #
# Global rider-code registry
# --------------------------------------------------------------------------- #
def assign_rider_codes(riders: dict[str, dict]) -> dict[str, str]:
    """rider_id → stable 3+ char code. Deterministic in rider_id order.

    Base is the ASCII surname's first three letters, uppercased. On collision
    between *different* riders, disambiguate with the first-name initial, then a
    numeric suffix — always the same result for the same input set.
    """
    codes: dict[str, str] = {}
    used: dict[str, str] = {}  # code → rider_id owner
    for rid in sorted(riders):
        info = riders[rid]
        surname = _ascii(rider_surname(info["full_name"])).upper()
        first = _ascii((info["full_name"] or " ").strip().split(" ")[0])
        base = (surname[:3] or "RDR").ljust(3, "X")
        cand = base
        if used.get(cand, rid) != rid:
            cand = (surname[:2] + first[:1]).upper().ljust(3, "X")
        n = 2
        while used.get(cand, rid) != rid:
            cand = f"{base[:2]}{n}"
            n += 1
        codes[rid] = cand
        used[cand] = rid
    return codes


# --------------------------------------------------------------------------- #
def _classify(api: MotoGPApi, session: dict | None) -> list[dict]:
    """Normalise a session's classification into ordered rider rows."""
    if not session:
        return []
    rows = api.classification(session["id"])
    out = []
    for r in rows:
        rider = r.get("rider") or {}
        rid = rider.get("id")
        pos = r.get("position")
        if not rid:
            continue
        out.append(
            {
                "rider_id": rid,
                "full_name": rider.get("full_name"),
                "number": rider.get("number"),
                "country": (rider.get("country") or {}).get("iso"),
                "manufacturer": (r.get("constructor") or {}).get("name"),
                "team": (r.get("team") or {}).get("name"),
                "position": int(pos) if pos else None,
                "status": r.get("status"),
                "points": r.get("points"),
            }
        )
    out.sort(key=lambda x: (x["position"] is None, x["position"] or 999))
    return out


def _grid_from_quali(picked: dict, api: MotoGPApi, code_of) -> list[str]:
    """Reconstruct the starting grid order (codes) from Q2 then Q1."""
    q2 = _classify(api, picked.get("q2"))
    q1 = _classify(api, picked.get("q1"))
    order: list[str] = []
    seen: set[str] = set()
    for row in q2 + q1:
        c = code_of(row["rider_id"])
        if c and c not in seen:
            order.append(c)
            seen.add(c)
    return order


def _full_calendar(api: MotoGPApi, season_uuid: str) -> list[dict]:
    """Every Grand Prix on the calendar (finished + upcoming), date-ordered.

    Upcoming rounds carry no results but the site needs them for the schedule and
    the model needs the *next* venue to forecast. Round numbers are assigned over
    the full season so an upcoming round keeps a stable number as it completes.
    """
    events = api.events(season_uuid, finished_only=False)
    out = []
    for i, ev in enumerate(events, start=1):
        circuit = ev.get("circuit") or {}
        out.append(
            {
                "round": i,
                "name": ev.get("sponsored_name") or ev.get("name"),
                "shortName": ev.get("short_name"),
                "venue": circuit.get("name"),
                "place": circuit.get("place"),
                "country": (ev.get("country") or {}).get("iso"),
                "date": ev.get("date_end") or ev.get("date_start"),
                "dateStart": ev.get("date_start"),
            }
        )
    return out


def build_season(api: MotoGPApi, year: int, code_of) -> dict:
    season_uuid = api.season_uuid(year)
    if not season_uuid:
        raise SystemExit(f"season {year} not found in API")
    cat = api.premier_category_uuid(season_uuid)
    if not cat:
        raise SystemExit(f"premier category not found for {year}")
    events = api.events(season_uuid, finished_only=True)
    full_calendar = _full_calendar(api, season_uuid)

    calendar: list[dict] = []
    results: dict[str, dict] = {}
    qualifying: dict[str, list[str]] = {}
    rider_pts: dict[str, float] = {}
    rider_meta: dict[str, dict] = {}
    manu_pts: dict[str, float] = {}

    rnd = 0
    for ev in events:
        sess = api.sessions(ev["id"], cat)
        picked = _pick_sessions(sess)
        race = _classify(api, picked.get("race"))
        if not race:
            continue  # not actually run/scored yet — keeps completed set honest
        rnd += 1
        sprint = _classify(api, picked.get("sprint"))
        grid = _grid_from_quali(picked, api, code_of)

        circuit = ev.get("circuit") or {}
        calendar.append(
            {
                "round": rnd,
                "name": ev.get("sponsored_name") or ev.get("name"),
                "shortName": ev.get("short_name"),
                "venue": circuit.get("name"),
                "country": (ev.get("country") or {}).get("iso"),
                "date": ev.get("date_end") or ev.get("date_start"),
                "completed": True,
                "hasSprint": bool(sprint),
            }
        )

        def _rows(cls, table):
            rows = []
            for r in cls:
                code = code_of(r["rider_id"])
                pts = r["points"]
                if pts is None and r["position"] in table:
                    pts = table[r["position"]]
                rows.append(
                    {
                        "code": code,
                        "position": r["position"],
                        "status": r["status"],
                        "points": pts or 0,
                        "manufacturer": r["manufacturer"],
                        "team": r["team"],
                    }
                )
                # standings + roster accrual
                rider_meta[code] = {
                    "code": code,
                    "name": r["full_name"],
                    "number": r["number"],
                    "nationality": r["country"],
                    "manufacturer": r["manufacturer"],
                    "team": r["team"],
                }
                rider_pts[code] = rider_pts.get(code, 0) + (pts or 0)
                if r["manufacturer"]:
                    manu_pts[r["manufacturer"]] = manu_pts.get(r["manufacturer"], 0) + (pts or 0)
            return rows

        results[str(rnd)] = {
            "sprint": _rows(sprint, _SPR_POINTS),
            "feature": _rows(race, _GP_POINTS),
        }
        if grid:
            qualifying[str(rnd)] = grid

    driver_standings = sorted(
        (
            {**rider_meta[c], "points": round(rider_pts[c], 1)}
            for c in rider_pts
        ),
        key=lambda d: -d["points"],
    )
    team_standings = sorted(
        ({"name": m, "points": round(p, 1)} for m, p in manu_pts.items()),
        key=lambda d: -d["points"],
    )
    return {
        "season": year,
        "source": "api.motogp.pulselive.com",
        "sport": "MotoGP",
        "totalRounds": len(full_calendar) or len(calendar),
        "completedRounds": [c["round"] for c in calendar],
        "calendar": calendar,
        "fullCalendar": full_calendar,
        "riders": list(rider_meta.values()),
        "manufacturers": sorted(manu_pts, key=lambda m: -manu_pts[m]),
        "driverStandings": driver_standings,
        "teamStandings": team_standings,
        "results": results,
        "qualifying": qualifying,
    }


def _parse_seasons(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build committed MotoGP snapshots from the results API.")
    ap.add_argument("--seasons", default="2021-2026", help="e.g. 2021-2026 or 2024,2025")
    ap.add_argument("--current", type=int, default=2026, help="season written to official_<year>.json")
    args = ap.parse_args()

    api = MotoGPApi()
    years = _parse_seasons(args.seasons)

    # Pass 1: global rider registry (stable codes across all seasons).
    riders: dict[str, dict] = {}
    per_season_events: dict[int, tuple[str, list[dict]]] = {}
    for y in years:
        su = api.season_uuid(y)
        cat = api.premier_category_uuid(su) if su else None
        if not (su and cat):
            print(f"  ! {y}: no season/category, skipping")
            continue
        evs = api.events(su, finished_only=True)
        per_season_events[y] = (cat, evs)
        for ev in evs:
            for s in api.sessions(ev["id"], cat):
                if s.get("type") in ("RAC", "SPR"):
                    for r in api.classification(s["id"]):
                        rd = r.get("rider") or {}
                        if rd.get("id"):
                            riders.setdefault(rd["id"], {"full_name": rd.get("full_name")})
    codes = assign_rider_codes(riders)
    print(f"registry: {len(codes)} riders across {years}")

    def code_of(rid: str) -> str | None:
        return codes.get(rid)

    (_DATA_DIR / "history").mkdir(parents=True, exist_ok=True)
    for y in years:
        snap = build_season(api, y, code_of)
        if y == args.current:
            path = _DATA_DIR / f"official_{y}.json"
        else:
            path = _DATA_DIR / "history" / f"{y}.json"
        path.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  {y}: {snap['totalRounds']} rounds, {len(snap['riders'])} riders "
              f"-> {path.relative_to(_DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
