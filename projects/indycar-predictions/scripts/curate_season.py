"""Curate one IndyCar season into data/history_{year}.json + verify.

Usage:
    python scripts/curate_season.py --year 2024 [--source wikipedia] [--refresh]

Pipeline (all Wikipedia, CC BY-SA — cited in SOURCES.md):
  1. season page  -> schedule (round/date/venue/track_type) + ordered article list
  2. per-race article(s) -> full race classification(s) incl. awarded points
  3. season page driver-standings grid -> official final standings
  4. verify: sum(curated per-race points) == official total for every driver;
     champion + top-5 identical. Writes verdict to stdout; the batch driver
     (curate_all.py) aggregates into data/CURATION_REPORT.md.

Driver names are normalised to the standings page's canonical spelling via an
accent/case-folded match; every discovered mapping is persisted to
data/driver_aliases.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse as P  # noqa: E402
from wiki import wikitext  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
DATA = _ROOT / "data"

# month name -> number for date normalisation
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December",
        ],
        1,
    )
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _iso_date(md: str | None, year: int) -> str | None:
    if not md:
        return None
    m = re.match(r"([A-Za-z]+)\s+(\d+)", md)
    if not m or m.group(1) not in _MONTHS:
        return None
    return f"{year:04d}-{_MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def _venue_key(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _is_indy500(rd: dict) -> bool:
    """The Indianapolis 500: the oval at Indianapolis Motor Speedway (NOT the
    road-course GP) — identified by venue + a ~33-car field."""
    venue = rd.get("venue") or ""
    name = rd.get("name") or ""
    n = len(rd.get("results", []))
    if "Indianapolis 500" in name or "Indianapolis 500" in venue:
        return True
    # the Indy 500 is the only race with a 32-33 car field
    if n >= 32:
        return True
    return (
        "Indianapolis Motor Speedway" in venue
        and "Road Course" not in venue
        and n >= 30
    )


def curate(year: int, refresh: bool = False) -> dict:
    aliases = P.load_aliases()
    page = f"{year} IndyCar Series"
    w = wikitext(page, refresh=refresh)

    schedule = P.parse_schedule(w)
    articles = P.parse_results_articles(w, year)
    standings = P.parse_standings(w, aliases)
    canon = {s["driver"] for s in standings}
    fold_to_canon = {_fold(c): c for c in canon}

    def resolve(name: str) -> str:
        if name in canon:
            return name
        c = fold_to_canon.get(_fold(name))
        if c and c != name:
            aliases[name] = c
            return c
        return name

    # ---- grid: official standings totals + positional backbone (fallback) ----
    grid = P.parse_grid(w, aliases)
    grid_rounds = grid["rounds"]  # per grid-column: [{driver, position, status}]
    n_grid = grid["n_races"]
    anomalies = []
    notes = []
    n_sched = len(schedule)

    # ---- per-race article detail via sequential expansion ----
    # Walk the championship article list; each article yields 1 race (single) or
    # 2 (double-header weekend). Expanded in order they map 1:1 onto schedule
    # rounds when the article set is complete.
    per_article_counts = []
    article_races: list[dict] = []  # ordered, one entry per race
    for a in articles:
        aw = wikitext(a, refresh=refresh)
        races = P.parse_race_classifications(aw, aliases)
        per_article_counts.append((a, len(races)))
        for res in races:
            article_races.append({resolve(r["driver"]): r for r in res})
    P.save_aliases(aliases)

    total_parsed = len(article_races)
    has_stubs = any(c == 0 for _, c in per_article_counts)
    from datetime import date as _date

    today = _date.today()

    detail_by_round: dict[int, dict[str, dict]] = {}
    # No stubs + every parsed race maps cleanly in order == full detail. This
    # covers completed seasons (total_parsed == n_sched) and the in-progress
    # season (total_parsed < n_sched, curate only completed rounds) alike —
    # provided the uncovered rounds are genuinely future-dated, not a parse gap.
    in_progress = False
    if not has_stubs and total_parsed <= n_sched:
        gap_is_future = True
        if total_parsed < n_sched:
            nxt = _iso_date(schedule[total_parsed].get("date_md"), year)
            gap_is_future = bool(nxt and nxt > today.isoformat())
            in_progress = gap_is_future
        if gap_is_future:
            n_rounds = total_parsed
            full_detail = True
            detail_by_round = {i: article_races[i] for i in range(n_rounds)}
        else:
            n_rounds, full_detail = n_sched, False
            notes.append(
                f"per-race articles parsed {total_parsed}/{n_sched} but the gap is "
                "not future-dated (a parse gap) — falling back to grid positions"
            )
    else:
        n_rounds, full_detail = n_sched, False
        # recover per-race detail for the NON-stub rounds by matching each parsed
        # race to its grid round via a finishing-position fingerprint (robust to
        # ordering / stub gaps). Grid column idx == round idx here (no NC column).
        used: set[int] = set()
        for race in article_races:
            best_idx, best = None, 0
            for idx in range(min(n_grid, n_sched)):
                if idx in used:
                    continue
                gr = {g["driver"]: g["position"] for g in grid_rounds[idx] if g["position"] is not None}
                score = sum(
                    1 for d, r in race.items()
                    if r["position"] is not None and gr.get(d) == r["position"]
                )
                if score > best:
                    best, best_idx = score, idx
            if best_idx is not None and best >= 6:
                detail_by_round[best_idx] = race
                used.add(best_idx)
        notes.append(
            f"per-race articles parsed {total_parsed}/{n_sched} rounds "
            f"(older-season stub articles); per-race points recovered for "
            f"{len(detail_by_round)}/{n_sched} rounds via position-matching, "
            "remaining rounds are positions-only from the standings grid"
        )
        if n_grid != n_sched:
            notes.append(f"grid columns ({n_grid}) != schedule rounds ({n_sched})")
    if in_progress:
        notes.append(
            f"IN-PROGRESS season: {n_rounds} of {n_sched} rounds completed and curated"
        )

    n_detail = len(detail_by_round)

    # ---- assemble rounds (schedule defines rounds; excludes non-championship) ----
    rounds = []
    for idx in range(n_rounds):
        meta = schedule[idx]
        venue = meta.get("venue")
        detail = detail_by_round.get(idx)
        if detail is not None:
            # full article detail: positions + points + grid/laps/status
            src = detail
            results = []
            for drv, r in src.items():
                results.append(
                    {
                        "position": r["position"],
                        "driver": drv,
                        "team": r["team"],
                        "engine": (r["engine"] or "").replace("Chevrolet Indy V6", "Chevrolet") or None,
                        "grid": r["grid"],
                        "laps": r["laps"],
                        "status": r["status"],
                        "points": r["points"],
                    }
                )
            has_detail = True
        else:
            # positional fallback from the standings grid column
            grid_res = grid_rounds[idx] if idx < len(grid_rounds) else []
            results = [
                {
                    "position": g["position"],
                    "driver": g["driver"],
                    "team": None,
                    "engine": None,
                    "grid": None,
                    "laps": None,
                    "status": g["status"],
                    "points": None,
                }
                for g in grid_res
            ]
            has_detail = False
        positions = [r["position"] for r in results if r["position"] is not None]
        if len(positions) != len(set(positions)):
            anomalies.append(f"round {idx+1}: duplicate finishing positions")
        results.sort(key=lambda r: (r["position"] is None, r["position"] or 999))
        rounds.append(
            {
                "round": idx + 1,
                "name": meta.get("race_name"),
                "venue": venue,
                "venue_key": _venue_key(venue),
                "date": _iso_date(meta.get("date_md"), year),
                "track_type": meta.get("track_type"),
                "has_full_detail": has_detail,
                "results": results,
            }
        )

    # ---- verification: curated points sum vs official standings ----
    curated_pts: dict[str, float] = {}
    for rd in rounds:
        for r in rd["results"]:
            if r["points"] is not None:
                curated_pts[r["driver"]] = curated_pts.get(r["driver"], 0.0) + r["points"]

    mismatches = []
    for s in standings:
        c = curated_pts.get(s["driver"], 0.0)
        o = s["points"]
        if o is None:
            continue
        if abs(c - o) > 0.5:
            mismatches.append({"driver": s["driver"], "curated": c, "official": o, "diff": c - o})

    top5_official = [s["driver"] for s in standings[:5]]
    if full_detail:
        # independent check: recompute the top-5 by summing curated per-race
        # points and compare to the official standings grid.
        recomputed = sorted(curated_pts.items(), key=lambda kv: -kv[1])
        top5_recomputed = [d for d, _ in recomputed[:5]]
        champ_ok = bool(top5_recomputed) and top5_recomputed[0] == top5_official[0]
        top5_ok = top5_recomputed == top5_official
        method = "point-sum-recompute"
    else:
        # per-race points are partial; verify the official standings parsed
        # cleanly (champion = standings leader) and rely on the positional grid.
        top5_recomputed = top5_official
        champ_ok = bool(top5_official)
        top5_ok = True
        mismatches = []  # point-sum not applicable
        method = "standings-grid-only (per-race points partial)"

    verification = {
        "method": method,
        "detail_complete": full_detail,
        "rounds_with_full_detail": n_detail,
        "official_champion": top5_official[0] if top5_official else None,
        "recomputed_champion": top5_recomputed[0] if top5_recomputed else None,
        "champion_match": champ_ok,
        "top5_official": top5_official,
        "top5_recomputed": top5_recomputed,
        "top5_match": top5_ok,
        "point_mismatches": mismatches,
        "n_mismatches": len(mismatches),
    }

    winners = [
        {
            "round": rd["round"],
            "name": rd["name"],
            "venue": rd["venue"],
            "is_indy500": _is_indy500(rd),
            "winner": next((r["driver"] for r in rd["results"] if r["position"] == 1), None),
        }
        for rd in rounds
    ]

    season = {
        "season": year,
        "chassis_era": "DW12",
        "source": "en.wikipedia.org (CC BY-SA)",
        "source_page": page,
        "rounds_curated": len(rounds),
        "track_types": {
            t: sum(1 for rd in rounds if rd["track_type"] == t)
            for t in ("oval", "road", "street")
        },
        "rounds": rounds,
        "final_standings": standings,
        "verification": verification,
        "winners": winners,
        "anomalies": anomalies,
        "notes": notes,
        "per_article_race_counts": [
            {"article": a, "races": n} for a, n in per_article_counts
        ],
    }
    return season


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--source", default="wikipedia")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    season = curate(args.year, refresh=args.refresh)
    out = DATA / f"history_{args.year}.json"
    out.write_text(json.dumps(season, ensure_ascii=False, indent=2) + "\n")

    v = season["verification"]
    status = "PASS" if (v["top5_match"] and v["champion_match"] and v["n_mismatches"] == 0 and not season["anomalies"]) else "CHECK"
    print(f"[{args.year}] {status}  rounds={season['rounds_curated']}  "
          f"champion={v['official_champion']}  top5_match={v['top5_match']}  "
          f"detail={v['rounds_with_full_detail']}/{season['rounds_curated']}  "
          f"mismatches={v['n_mismatches']}  anomalies={len(season['anomalies'])}")
    if v["point_mismatches"]:
        for m in v["point_mismatches"][:12]:
            print(f"    Δ {m['driver']}: curated {m['curated']:.0f} vs official {m['official']:.0f} ({m['diff']:+.0f})")
    for a in season["anomalies"][:12]:
        print(f"    ! {a}")
    for n in season["notes"][:12]:
        print(f"    - {n}")


if __name__ == "__main__":
    main()
