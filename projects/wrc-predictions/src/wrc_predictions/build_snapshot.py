"""Build committed WRC snapshots from the official wrc.com results API.

For each season, walks the calendar (``seasonRounds``) + the Drivers (333) and
Manufacturers (335) championships, pivots every entrant's ``roundResults`` by
``eventId`` to reconstruct each rally's full classification, and writes one
canonical snapshot per season in the shape the golden-template snapshot source
consumes. Rally has ONE scored classification per round (stored under the
``"rally"`` key), plus the defining rally variable — the **surface**
(gravel / tarmac / snow) — attached to every round from a curated map, since the
API does not expose it.

Driver **codes** are assigned once, globally, deterministically (surname TLA with
first-initial disambiguation), so a crew keeps the same code across seasons.

Run (network, one-off / cron):
    PYTHONPATH=src ../../.venv/bin/python -m wrc_predictions.build_snapshot --seasons 2021-2026
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from .sources.redbull_source import DRIVERS_CHAMP, MANUFACTURERS_CHAMP, WrcApi

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# WRC finishing-points table (Rally1 overall, base finishing points; Super Sunday
# + Power Stage bonuses are folded into the API's real season totals, which we use
# verbatim for standings — this table only feeds the championship projection).
WRC_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

# Surface is THE rally variable (a snow specialist is not a Safari specialist), but
# the API omits it — so this curated map, keyed by substrings of the official rally
# name, attaches it. Well-known characteristics, not invented data. Default gravel.
_SURFACE_RULES: list[tuple[tuple[str, ...], str]] = [
    (("sweden", "arctic"), "snow"),
    (("monte carlo", "monte-carlo", "montecarlo"), "tarmac"),
    (("croatia", "japan", "spain", "catalunya", "españa", "espana", "belgium",
      "ypres", "monza", "central europe", "germany", "deutschland", "corsica",
      "france", "canarias", "canary"), "tarmac"),
    (("kenya", "safari", "portugal", "greece", "acropolis", "estonia", "finland",
      "paraguay", "chile", "sardegna", "italia", "italy", "saudi", "mexico",
      "méxico", "new zealand", "turkey", "wales", "britain", "australia",
      "poland"), "gravel"),
]


def surface_for(name: str) -> str:
    low = (name or "").lower()
    for keys, surf in _SURFACE_RULES:
        if any(k in low for k in keys):
            return surf
    return "gravel"


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")


def assign_codes(people: dict[str, dict]) -> dict[str, str]:
    """personId -> stable code. Deterministic; surname TLA, disambiguated."""
    codes: dict[str, str] = {}
    used: dict[str, str] = {}
    for pid in sorted(people, key=str):
        info = people[pid]
        surname = _ascii(info.get("last", "")).upper()
        first = _ascii(info.get("first", " "))
        base = (surname[:3] or "DRV").ljust(3, "X")
        cand = base
        if used.get(cand, pid) != pid:
            cand = (surname[:2] + first[:1]).upper().ljust(3, "X")
        n = 2
        while used.get(cand, pid) != pid:
            cand = f"{base[:2]}{n}"
            n += 1
        codes[pid] = cand
        used[cand] = pid
    return codes


def _country_name(iso3: str | None) -> str | None:
    return iso3 or None


def build_season(api: WrcApi, year: int, code_of) -> dict:
    season_id = api.wrc_season_id(year)
    if not season_id:
        raise SystemExit(f"WRC season {year} not found")
    detail = api.season_detail(season_id)
    rounds = sorted(detail.get("seasonRounds", []), key=lambda r: r.get("order", 0))
    drv_champ = api.championship_id(season_id, DRIVERS_CHAMP)
    man_champ = api.championship_id(season_id, MANUFACTURERS_CHAMP)

    ddet = api.championship_detail(drv_champ, season_id) if drv_champ else {}
    dres = api.championship_results(drv_champ, season_id) if drv_champ else {}
    entries = {e["championshipEntryId"]: e for e in ddet.get("championshipEntries", [])}

    def entry_meta(cid):
        e = entries.get(cid, {})
        pid = str(e.get("personId", cid))
        return {
            "personId": pid,
            "code": code_of(pid),
            "first": e.get("fieldOne", ""),
            "last": e.get("fieldTwo", ""),
            "name": f"{e.get('fieldOne', '')} {(e.get('fieldTwo') or '').title()}".strip(),
            "nationality": e.get("fieldThree"),
            "manufacturer": e.get("fieldFour") or "Privateer",
        }

    # event_id -> round order, and event meta
    ev_round = {r["eventId"]: r.get("order") for r in rounds}
    def _country(ev: dict) -> str | None:
        c = ev.get("country")
        if isinstance(c, dict):
            return c.get("name") or c.get("iso3")
        return c or ev.get("countryName")

    round_meta = {
        r.get("order"): {
            "eventId": r["eventId"],
            "name": (r.get("event") or {}).get("name") or f"Round {r.get('order')}",
            "shortName": (r.get("event") or {}).get("name", "")[:14],
            "country": _country(r.get("event") or {}),
            "date": (r.get("event") or {}).get("startDate"),
        }
        for r in rounds
    }

    # pivot driver roundResults -> per-round classification
    byround: dict[int, list[dict]] = {}
    rider_meta: dict[str, dict] = {}
    driver_pts: dict[str, float] = {}
    for ent in dres.get("entryResults", []):
        cid = ent["championshipEntryId"]
        meta = entry_meta(cid)
        code = meta["code"]
        rider_meta[code] = meta
        driver_pts[code] = float(ent.get("overallPoints") or 0)
        for rr in ent.get("roundResults", []):
            if rr.get("publishedStatus") != "Published":
                continue
            rnd = ev_round.get(rr.get("eventId"))
            pos = rr.get("position")
            if rnd is None or not str(pos).isdigit():
                continue
            byround.setdefault(rnd, []).append({
                "code": code,
                "position": int(pos),
                "status": rr.get("status") or "Finished",
                "points": rr.get("totalPoints") or 0,
                "manufacturer": meta["manufacturer"],
            })

    completed = sorted(byround)
    calendar = []
    for order in sorted(round_meta):
        m = round_meta[order]
        calendar.append({
            "round": order,
            "eventId": m["eventId"],
            "name": m["name"],
            "shortName": m["shortName"],
            "country": m["country"],
            "date": m["date"],
            "surface": surface_for(m["name"]),
            "completed": order in byround,
        })

    results = {
        str(rnd): {"rally": sorted(byround[rnd], key=lambda x: x["position"])}
        for rnd in completed
    }

    # manufacturer standings (championship 335, real totals)
    man_standings = []
    if man_champ:
        mres = api.championship_results(man_champ, season_id)
        mdet = api.championship_detail(man_champ, season_id)
        mnames = {e["championshipEntryId"]: (e.get("fieldOne") or e.get("fieldTwo") or "?")
                  for e in mdet.get("championshipEntries", [])}
        for ent in sorted(mres.get("entryResults", []), key=lambda e: e.get("overallPosition", 99)):
            man_standings.append({
                "name": mnames.get(ent["championshipEntryId"], "?"),
                "points": float(ent.get("overallPoints") or 0),
            })

    manufacturers = sorted({m["manufacturer"] for m in rider_meta.values()
                            if m["manufacturer"] and m["manufacturer"] != "Privateer"})
    driver_standings = sorted(
        ({**rider_meta[c], "points": round(driver_pts[c], 1)} for c in driver_pts),
        key=lambda d: -d["points"],
    )
    for i, d in enumerate(driver_standings, 1):
        d["position"] = i

    return {
        "season": year,
        "source": "wrc.com (Red Bull results API)",
        "sport": "WRC",
        "totalRounds": len(calendar),
        "completedRounds": completed,
        "calendar": calendar,
        "fullCalendar": calendar,
        "drivers": [{"code": m["code"], "name": m["name"], "firstName": m["first"],
                     "lastName": (m["last"] or "").title(), "nationality": m["nationality"],
                     "manufacturer": m["manufacturer"]} for m in rider_meta.values()],
        "manufacturers": manufacturers,
        "driverStandings": driver_standings,
        "manufacturerStandings": man_standings,
        "results": results,
    }


def _persons_for_season(api: WrcApi, year: int) -> dict[str, dict]:
    season_id = api.wrc_season_id(year)
    if not season_id:
        return {}
    champ = api.championship_id(season_id, DRIVERS_CHAMP)
    if not champ:
        return {}
    det = api.championship_detail(champ, season_id)
    out = {}
    for e in det.get("championshipEntries", []):
        pid = str(e.get("personId", e.get("championshipEntryId")))
        out[pid] = {"first": e.get("fieldOne", ""), "last": e.get("fieldTwo", "")}
    return out


def _parse_seasons(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build committed WRC snapshots from the results API.")
    ap.add_argument("--seasons", default="2021-2026")
    ap.add_argument("--current", type=int, default=2026)
    args = ap.parse_args()
    api = WrcApi()
    years = _parse_seasons(args.seasons)

    # global person registry -> stable codes
    people: dict[str, dict] = {}
    for y in years:
        people.update(_persons_for_season(api, y))
    codes = assign_codes(people)
    print(f"registry: {len(codes)} drivers across {years}")

    (_DATA_DIR / "history").mkdir(parents=True, exist_ok=True)
    for y in years:
        snap = build_season(api, y, lambda pid: codes.get(str(pid)))
        path = (_DATA_DIR / f"official_{y}.json") if y == args.current \
            else (_DATA_DIR / "history" / f"{y}.json")
        path.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"  {y}: {len(snap['completedRounds'])}/{snap['totalRounds']} rounds, "
              f"{len(snap['drivers'])} drivers -> {path.relative_to(_DATA_DIR.parent)}")


if __name__ == "__main__":
    main()
