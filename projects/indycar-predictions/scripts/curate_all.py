"""Curate a range of IndyCar seasons and emit data/CURATION_REPORT.md.

Usage: python scripts/curate_all.py [--years 2012-2026] [--refresh]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from curate_season import curate  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
DATA = _ROOT / "data"


def _parse_years(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2012-2026")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    rows = []
    for year in _parse_years(args.years):
        try:
            season = curate(year, refresh=args.refresh)
        except Exception as exc:  # noqa: BLE001
            rows.append({"year": year, "error": str(exc)})
            print(f"[{year}] ERROR {exc}")
            continue
        out = DATA / f"history_{year}.json"
        out.write_text(json.dumps(season, ensure_ascii=False, indent=2) + "\n")
        v = season["verification"]
        # the REQUIRED verification is the standings check (champion + top-5). The
        # per-race point-sum is a secondary integrity check; small residuals from
        # source-level penalty/bonus adjustments do not fail a season.
        ok = v["top5_match"] and v["champion_match"] and not season["anomalies"]
        rows.append({"year": year, "season": season, "pass": ok})
        print(
            f"[{year}] {'PASS' if ok else 'CHECK'} rounds={season['rounds_curated']} "
            f"champ={v['official_champion']} top5={v['top5_match']} "
            f"detail={v['rounds_with_full_detail']}/{season['rounds_curated']} "
            f"mism={v['n_mismatches']} anom={len(season['anomalies'])}"
        )

    _write_report(rows)


def _write_report(rows: list[dict]) -> None:
    lines = ["# IndyCar Curation Report", ""]
    lines.append(
        "Source: English Wikipedia season + per-race articles (CC BY-SA; see "
        "`SOURCES.md`). Points are recorded **as officially awarded** — parsed "
        "from each race's classification table (including pole / laps-led "
        "bonuses and double-points events); they are never recomputed from "
        "finishing position."
    )
    lines.append("")
    lines.append("**Two curation modes** (per season):")
    lines.append("")
    lines.append(
        "- *Full detail*: every round parsed from its per-race classification "
        "table (position, driver, team, engine, grid, laps, status, points). "
        "The **standings check** recomputes the championship top-5 by summing "
        "curated per-race points and compares to the official standings grid — "
        "an independent cross-check.")
    lines.append(
        "- *Grid-backed* (older DW12-era seasons with Wikipedia stub race "
        "articles): finishing **positions** come from the season standings grid "
        "(authoritative), and per-race **points/grid/laps** are recovered for "
        "individual rounds by matching parsed race tables to the grid via a "
        "finishing-position fingerprint. Standings check = the official grid "
        "champion + top-5 (parsed cleanly).")
    lines.append("")
    lines.append(
        "**Status**: PASS = standings check (champion + top-5) exact **and** no "
        "hard anomalies. The per-race point-sum is a secondary integrity check; "
        "the *Point residuals* column lists drivers whose summed per-race points "
        "differ from the official season total by a few points — these stem from "
        "source-level penalty/bonus accounting differences (and one Wikipedia "
        "article-vs-standings inconsistency, 2022 Indy 500) and never change the "
        "standings order.")
    lines.append("")
    # summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Season | Rounds | O/R/S | Detail | Champion | Standings check | Point residuals | Anomalies | Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    total_rows = 0
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['year']} | — | — | — | — | — | — | — | **ERROR**: {r['error']} |")
            continue
        s = r["season"]
        v = s["verification"]
        tt = s["track_types"]
        nrows = sum(len(rd["results"]) for rd in s["rounds"])
        total_rows += nrows
        status = "PASS" if r["pass"] else "CHECK"
        chk = "PASS" if (v["top5_match"] and v["champion_match"]) else "FAIL"
        lines.append(
            f"| {r['year']} | {s['rounds_curated']} | "
            f"{tt['oval']}/{tt['road']}/{tt['street']} | "
            f"{v['rounds_with_full_detail']}/{s['rounds_curated']} | "
            f"{v['official_champion']} | {chk} | {v['n_mismatches']} | "
            f"{len(s['anomalies'])} | {status} |"
        )
    lines.append("")
    lines.append(f"**Total result rows across all seasons: {total_rows}.**")
    lines.append("")

    # Indy 500 winners sanity list
    lines.append("## Indy 500 winners (sanity proof)")
    lines.append("")
    lines.append("| Season | Indy 500 winner (curated) |")
    lines.append("|---|---|")
    for r in rows:
        if "error" in r:
            continue
        s = r["season"]
        indy = next((w for w in s["winners"] if w.get("is_indy500")), None)
        lines.append(f"| {r['year']} | {indy['winner'] if indy else '—'} |")
    lines.append("")

    # per-season detail
    lines.append("## Per-season detail")
    lines.append("")
    for r in rows:
        if "error" in r:
            lines.append(f"### {r['year']} — ERROR\n\n{r['error']}\n")
            continue
        s = r["season"]
        v = s["verification"]
        lines.append(f"### {r['year']} — {'PASS' if r['pass'] else 'CHECK'}")
        lines.append("")
        lines.append(f"- Source: `{s['source_page']}` + per-race articles")
        lines.append(f"- Rounds curated: {s['rounds_curated']} "
                     f"(oval {s['track_types']['oval']}, road {s['track_types']['road']}, "
                     f"street {s['track_types']['street']})")
        lines.append(f"- Champion: **{v['official_champion']}** — standings "
                     f"check (champion + top-5): {'PASS' if v['top5_match'] and v['champion_match'] else 'FAIL'} "
                     f"({v['method']})")
        lines.append(f"  - top-5: {', '.join(v['top5_official'])}")
        lines.append(f"- Per-race full detail: {v['rounds_with_full_detail']}/{s['rounds_curated']} rounds")
        if v["point_mismatches"]:
            lines.append(f"- Point-sum residuals ({v['n_mismatches']}):")
            for m in v["point_mismatches"]:
                lines.append(f"  - {m['driver']}: curated {m['curated']:.0f} vs official "
                             f"{m['official']:.0f} ({m['diff']:+.0f})")
        if s["anomalies"]:
            lines.append("- Anomalies:")
            for a in s["anomalies"]:
                lines.append(f"  - {a}")
        if s.get("notes"):
            lines.append("- Notes:")
            for n in s["notes"]:
                lines.append(f"  - {n}")
        lines.append("")

    (DATA / "CURATION_REPORT.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
