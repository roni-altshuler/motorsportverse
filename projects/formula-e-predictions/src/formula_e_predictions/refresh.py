"""Refresh the committed real-data snapshot from the Pulselive API.

This is the *only* network-dependent step in the live FE pipeline (backfill is
its bulk-history sibling). It queries the official API once and writes a
deterministic, reviewable snapshot to ``data/official_<season>.json`` which
every downstream build reads offline. That keeps deploys reproducible and
immune to the live API being down or changing shape — re-run this script (with
network) to pull in newly-completed rounds. A failed live fetch is a no-op,
never bad data: the guards below refuse to write anything questionable.

Captured per season:
  * calendar   — the 17 points races (keys/dates from config), completed flags
                 + the API race ids;
  * results    — per completed round, the full race classification (incl.
                 retirements with status, grid, points, pole/FL flags);
  * qualifying — per round whose combined-qualifying session has run (incl.
                 the upcoming round, pre-race) — drives the post-quali forecast;
  * driverStandings / teamStandings — the **official** point totals (bonuses
                 included) and per-round progression from the standings API.

Guards (both root-caused from real incidents elsewhere in the monorepo):
  * wrong-event — every API race entry is cross-checked against the
    human-verified config calendar (date + season) before ingestion; a
    mismatch raises ``WrongEventError`` before ``main()`` ever writes;
  * empty-scrape regression — a refresh that would REDUCE the committed
    snapshot's completed-round count refuses to write (a transient empty
    response must never wipe real data).

Run:  PYTHONPATH=src python -m formula_e_predictions.refresh
          [--season 2026] [--out data/official_2026.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .sources.pulselive_source import PulseliveFESource, WrongEventError

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _default_out(season: int) -> Path:
    return _DATA_DIR / f"official_{season}.json"


def _points_history(race_standings: list[dict]) -> list[float]:
    """Cumulative championship points after each scored race, in race order."""
    entries = sorted(race_standings or [], key=lambda e: int(e.get("raceSequence") or 0))
    return [float(e.get("championshipPoints") or 0.0) for e in entries]


def _wins_podiums(results: dict, code: str) -> tuple[int, int]:
    wins = podiums = 0
    for block in results.values():
        for row in block.get("race", []):
            if row.get("code") == code and row.get("position"):
                if row["position"] == 1:
                    wins += 1
                if row["position"] <= 3:
                    podiums += 1
    return wins, podiums


def build_snapshot(season: int, *, source: PulseliveFESource | None = None) -> dict:
    src = source or PulseliveFESource()
    races = src.season_races(season)
    if races is None:
        raise RuntimeError("Pulselive race list unavailable — refusing to build a snapshot")

    # Config-calendar cross-check: the API's points-race count must match the
    # human-verified calendar. A mismatch means a cancelled/added event and a
    # human must re-verify round numbering before anything is ingested.
    if season == config.SEASON and len(races) != len(config.CALENDAR):
        raise WrongEventError(
            f"season {season}: API serves {len(races)} points races but the config "
            f"calendar has {len(config.CALENDAR)} — re-verify the calendar before refreshing"
        )

    results: dict[str, dict] = {}
    qualifying: dict[str, list[str]] = {}
    completed: list[int] = []
    for rnd in range(1, len(races) + 1):
        # Wrong-event guard: _race_for_round verifies each API entry against
        # config.CALENDAR_META (date + season) and raises WrongEventError on a
        # mismatch — a wrong event can never mutate the committed snapshot.
        quali = src.qualifying(season, rnd)
        if quali:
            qualifying[str(rnd)] = quali
        rows = src.race_rows(season, rnd)
        if not rows or not any(r.get("position") for r in rows):
            continue  # round not yet run (no classified finishers)
        completed.append(rnd)
        results[str(rnd)] = {"race": rows, "raceId": races[rnd - 1].get("id")}
        # Roster drift check: warn loudly on codes config knows nothing about
        # (a mid-season seat change needs a FORMER_DRIVERS entry).
        for r in rows:
            if season == config.SEASON and r["code"] not in config.TEAM_OF:
                print(
                    f"⚠️  round {rnd}: unknown driver code {r['code']} ({r['name']}) — "
                    "add the seat change to config (roster / FORMER_DRIVERS)."
                )

    drivers_api = src.driver_standings(season) or []
    teams_api = src.team_standings(season) or []

    drivers = []
    for d in sorted(drivers_api, key=lambda x: int(x.get("driverPosition") or 99)):
        code = (d.get("driverTLA") or "").strip().upper()
        team_raw = (d.get("driverTeamName") or "").strip()
        team = config.TEAM_ALIASES.get(team_raw, team_raw)
        wins, podiums = _wins_podiums(results, code)
        drivers.append(
            {
                "position": int(d.get("driverPosition") or 0),
                "code": code,
                "name": config.DRIVER_NAME.get(
                    code,
                    f"{(d.get('driverFirstName') or '').strip()} "
                    f"{(d.get('driverLastName') or '').strip()}".strip(),
                ),
                "team": config.TEAM_OF.get(code, team),
                "points": float(d.get("driverPoints") or 0.0),
                "wins": wins,
                "podiums": podiums,
                "pointsHistory": _points_history(d.get("driverRaceStandings") or []),
            }
        )

    teams = []
    for t in sorted(teams_api, key=lambda x: int(x.get("teamPosition") or 99)):
        team_raw = (t.get("teamName") or "").strip()
        teams.append(
            {
                "position": int(t.get("teamPosition") or 0),
                "team": config.TEAM_ALIASES.get(team_raw, team_raw),
                "points": float(t.get("teamPoints") or 0.0),
                "pointsHistory": _points_history(t.get("teamRaceStandings") or []),
            }
        )

    calendar = []
    for i, v in enumerate(config.CALENDAR, start=1):
        meta = config.CALENDAR_META.get(i, {})
        calendar.append(
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "kind": str(getattr(v.kind, "value", v.kind)),
                "city": meta.get("city", ""),
                "date": meta.get("date", ""),
                "completed": i in completed,
                "raceId": races[i - 1].get("id") if i <= len(races) else None,
            }
        )

    return {
        "season": season,
        "source": "api.formula-e.pulselive.com",
        "championshipId": config.CHAMPIONSHIP_IDS.get(season),
        "completedRounds": len(completed),
        "totalRounds": len(config.CALENDAR),
        "calendar": calendar,
        "driverStandings": drivers,
        "teamStandings": teams,
        "results": results,
        "qualifying": qualifying,
    }


def _existing_completed(path: Path, season: int) -> int:
    """completedRounds in the snapshot already on disk (0 if absent/unreadable)."""
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        return int(cur.get("completedRounds", 0)) if cur.get("season") == season else 0
    except Exception:
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Refresh the FE real-data snapshot from the Pulselive API"
    )
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--allow-regression",
        action="store_true",
        help="permit overwriting a snapshot with one that has FEWER completed rounds "
        "(default: refuse — guards against a transient empty live fetch wiping real data)",
    )
    args = ap.parse_args()
    out = args.out or _default_out(args.season)

    snap = build_snapshot(args.season)

    # Root-cause guard: a briefly-down API yields zero/fewer completed rounds.
    # NEVER let that regress a healthy committed snapshot — a refresh can only
    # ever add rounds, not lose them. The whole pipeline keys off
    # completedRounds, so a regression silently wipes the standings + the site.
    existing = _existing_completed(out, args.season)
    fresh = int(snap.get("completedRounds", 0))
    if fresh < existing and not args.allow_regression:
        print(
            f"⚠️  Refresh produced {fresh} completed round(s) but the existing snapshot "
            f"has {existing} — refusing to regress (live fetch likely empty/transient). "
            f"Keeping the committed snapshot. Use --allow-regression to override.",
            flush=True,
        )
        raise SystemExit(0)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Reconciliation report: official totals vs the sum of captured race points
    # (race rows carry bonus points, so the two must agree exactly).
    ok = True
    by_code: dict[str, float] = {}
    for block in snap["results"].values():
        for row in block["race"]:
            by_code[row["code"]] = by_code.get(row["code"], 0.0) + float(row.get("points") or 0.0)
    for d in snap["driverStandings"][:5]:
        s = by_code.get(d["code"], 0.0)
        flag = "" if abs(s - d["points"]) < 0.5 else "  <-- MISMATCH"
        ok = ok and not flag
        print(f"  {d['position']:>2} {d['code']} {d['points']:.0f} pts (Σrace={s:.0f}) {flag}")
    print(
        f"Wrote {out} — {snap['completedRounds']}/{snap['totalRounds']} rounds, "
        f"{len(snap['driverStandings'])} drivers, {len(snap['teamStandings'])} teams, "
        f"{len(snap['qualifying'])} qualifying sessions. reconciled={'yes' if ok else 'NO'}"
    )


if __name__ == "__main__":
    main()
