"""Refresh the committed real-data snapshot from fiaformula2.com.

This is the *only* network-dependent step in the F2 pipeline. It scrapes the
official site once and writes a deterministic, reviewable snapshot to
``data/official_2026.json`` which every downstream build reads offline. That
keeps deploys reproducible and immune to the live site being down or changing
markup — re-run this script (with network) to pull in newly-completed rounds.

Captured per season:
  * calendar   — 14 rounds (keys/names from config), with completed flags;
  * results    — per completed round, the sprint + feature classifications
                 (incl. retirements with status), from /Results?raceid=N;
  * qualifying — per round whose Friday session has run (incl. the upcoming
                 round, pre-race), the grid order — drives the post-quali forecast;
  * driverStandings / teamStandings — the **official** point totals and the
                 per-round score breakdown, from /Standings/{Driver,Team}.

Run:  PYTHONPATH=src python -m f2_predictions.refresh [--season 2026] [--out data/official_2026.json]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import config
from .sources.fia_f2_source import FiaF2Source

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_OUT = _DATA_DIR / "official_2026.json"

# Standings-page row extractors.
_RE_POS = re.compile(r'class="pos">\s*(\d+)\s*<')
_RE_CODE = re.compile(r'visible-desktop-down">\s*([A-Za-z]{2,4})\s*<')
_RE_NAME = re.compile(r'visible-desktop-up">\s*([^<]+?)\s*<')
_RE_TOTAL = re.compile(r'class="total-points">\s*([0-9]+)\s*<')
_RE_SCORE = re.compile(r'class="score[^"]*">\s*([^<]*?)\s*<')
_RE_TEAMNAME = re.compile(r'visible-desktop-up">\s*([^<]+?)\s*<')


def _fetch(url: str, timeout: int = 25) -> str | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        resp = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0 (motorsportverse/f2 research)"}, timeout=timeout
        )
        return resp.text if resp.status_code == 200 and resp.text else None
    except Exception:
        return None


def _score_pairs(row: str) -> list[tuple[float | None, float | None]]:
    """Per-round (sprint, feature) points from a standings row's score cells.

    The cells arrive as ``['', s1, f1, '', s2, f2, ...]`` (a separator per
    round); drop the empties, then pair them up. ``'-'``/empty → None.
    """
    cells = [c for c in _RE_SCORE.findall(row) if c != ""]

    def num(x: str) -> float | None:
        x = x.strip()
        if x in ("", "-"):
            return None
        try:
            return float(x)
        except ValueError:
            return None

    vals = [num(c) for c in cells]
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 1, 2)]


def _completed_perround(pairs: list[tuple[float | None, float | None]]) -> list[float]:
    """Cumulative total after each round that actually scored (non-None pair)."""
    history: list[float] = []
    running = 0.0
    for sp, ft in pairs:
        if sp is None and ft is None:
            continue
        running += (sp or 0.0) + (ft or 0.0)
        history.append(round(running, 1))
    return history


def _parse_driver_standings(page: str) -> list[dict]:
    i, j = page.find("<tbody"), page.find("</tbody>")
    body = page[i:j] if i != -1 else ""
    out: list[dict] = []
    for tr in re.split(r"<tr\b", body)[1:]:
        pos, code, total = _RE_POS.search(tr), _RE_CODE.search(tr), _RE_TOTAL.search(tr)
        if not (pos and code and total):
            continue
        name = _RE_NAME.search(tr)
        out.append(
            {
                "position": int(pos.group(1)),
                "code": code.group(1).upper(),
                "name": (name.group(1).strip() if name else code.group(1)),
                "points": float(total.group(1)),
                "perRound": _score_pairs(tr),
            }
        )
    return out


def _parse_team_standings(page: str) -> list[dict]:
    i, j = page.find("<tbody"), page.find("</tbody>")
    body = page[i:j] if i != -1 else ""
    out: list[dict] = []
    for tr in re.split(r"<tr\b", body)[1:]:
        pos, total = _RE_POS.search(tr), _RE_TOTAL.search(tr)
        name = _RE_TEAMNAME.search(tr)
        if not (pos and total and name):
            continue
        out.append(
            {
                "position": int(pos.group(1)),
                "team": name.group(1).strip(),
                "points": float(total.group(1)),
                "perRound": _score_pairs(tr),
            }
        )
    return out


def build_snapshot(season: int) -> dict:
    src = FiaF2Source()
    cal = src.calendar(season)  # [{round, raceid, country, city, dates}]
    by_round = {c["round"]: c for c in cal}

    results: dict[str, dict] = {}
    qualifying: dict[str, list[str]] = {}
    completed: list[int] = []
    for rnd in range(1, len(config.CALENDAR) + 1):
        entry = by_round.get(rnd)
        if not entry:
            continue
        page = src._page(entry["raceid"])
        if not page:
            continue
        # Capture qualifying whenever it is published — including the UPCOMING round
        # (Friday quali runs before the race), so the post-quali forecast can
        # condition on the real grid before any result exists.
        quali = src.qualifying(season, rnd)
        if quali:
            qualifying[str(rnd)] = quali
        sprint = FiaF2Source._parse_session(page, "Sprint Race", include_unclassified=True)
        feature = FiaF2Source._parse_session(page, "Feature Race", include_unclassified=True)
        if not any(r.get("position") for r in feature):
            continue  # round not yet run (no classified feature finishers)
        completed.append(rnd)
        results[str(rnd)] = {"sprint": sprint, "feature": feature, "raceid": entry["raceid"]}

    driver_page = _fetch(f"{config.FIA_F2_BASE_URL}/Standings/Driver")
    team_page = _fetch(f"{config.FIA_F2_BASE_URL}/Standings/Team")
    drivers = _parse_driver_standings(driver_page) if driver_page else []
    teams = _parse_team_standings(team_page) if team_page else []

    # Enrich driver rows with team + cumulative history; reconcile to the total.
    for d in drivers:
        d["team"] = config.TEAM_OF.get(d["code"], src.entry_list(season).get(d["code"], {}).get("team", ""))
        d["name"] = config.DRIVER_NAME.get(d["code"], d["name"])
        d["pointsHistory"] = _completed_perround(d["perRound"])
        d["wins"], d["podiums"] = _wins_podiums(results, d["code"])
    for t in teams:
        t["pointsHistory"] = _completed_perround(t["perRound"])

    calendar = []
    for i, v in enumerate(config.CALENDAR, start=1):
        meta = config.CALENDAR_META.get(i, {})
        calendar.append(
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "city": meta.get("city", ""),
                "sprintDate": meta.get("sprint", ""),
                "featureDate": meta.get("feature", ""),
                "completed": i in completed,
                "raceid": by_round.get(i, {}).get("raceid"),
            }
        )

    return {
        "season": season,
        "source": "fiaformula2.com",
        "completedRounds": len(completed),
        "totalRounds": len(config.CALENDAR),
        "calendar": calendar,
        "driverStandings": drivers,
        "teamStandings": teams,
        "results": results,
        "qualifying": qualifying,
    }


def _wins_podiums(results: dict, code: str) -> tuple[int, int]:
    wins = podiums = 0
    for block in results.values():
        for race in ("sprint", "feature"):
            for row in block.get(race, []):
                if row.get("code") == code and row.get("position"):
                    if row["position"] == 1:
                        wins += 1
                    if row["position"] <= 3:
                        podiums += 1
    return wins, podiums


def _existing_completed(path: Path, season: int) -> int:
    """completedRounds in the snapshot already on disk (0 if absent/unreadable)."""
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        return int(cur.get("completedRounds", 0)) if cur.get("season") == season else 0
    except Exception:
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh the F2 real-data snapshot from fiaformula2.com")
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    ap.add_argument(
        "--allow-regression",
        action="store_true",
        help="permit overwriting a snapshot with one that has FEWER completed rounds "
        "(default: refuse — guards against a transient empty live scrape wiping real data)",
    )
    args = ap.parse_args()

    snap = build_snapshot(args.season)

    # Root-cause guard against the failure that shipped an empty snapshot to main:
    # when the live site is briefly down or restructures, the scrape returns zero
    # completed rounds. NEVER let that regress a healthy committed snapshot — a
    # refresh can only ever add rounds, not lose them. The whole pipeline keys off
    # completedRounds, so a regression silently wipes the standings + the site.
    existing = _existing_completed(args.out, args.season)
    fresh = int(snap.get("completedRounds", 0))
    if fresh < existing and not args.allow_regression:
        print(
            f"⚠️  Refresh produced {fresh} completed round(s) but the existing snapshot "
            f"has {existing} — refusing to regress (live scrape likely empty/transient). "
            f"Keeping the committed snapshot. Use --allow-regression to override.",
            flush=True,
        )
        raise SystemExit(0)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Reconciliation report (totals must equal the sum of captured per-round points).
    ok = True
    for d in snap["driverStandings"][:5]:
        s = sum((sp or 0) + (ft or 0) for sp, ft in d["perRound"])
        flag = "" if abs(s - d["points"]) < 0.5 else "  <-- MISMATCH"
        ok = ok and not flag
        print(f"  {d['position']:>2} {d['code']} {d['points']:.0f} pts (Σ={s:.0f}) {flag}")
    print(
        f"Wrote {args.out} — {snap['completedRounds']}/{snap['totalRounds']} rounds, "
        f"{len(snap['driverStandings'])} drivers, {len(snap['teamStandings'])} teams. "
        f"reconciled={'yes' if ok else 'NO'}"
    )


if __name__ == "__main__":
    main()
