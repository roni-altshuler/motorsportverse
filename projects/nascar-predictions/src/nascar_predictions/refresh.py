"""Refresh the committed real-data snapshot from the cf.nascar.com feeds.

This is the *only* network-dependent step in the live NASCAR pipeline
(backfill is its bulk-history sibling). It queries the official feeds once and
writes a deterministic, reviewable snapshot to ``data/official_<season>.json``
which every downstream build reads offline. That keeps deploys reproducible
and immune to the live API being down or changing shape — re-run this script
(with network) to pull in newly-completed rounds. A failed live fetch is a
no-op, never bad data: the guards below refuse to write anything questionable.

Captured per season:
  * calendar   — the 36 points races (config-verified), completed flags;
  * results    — per completed round, the full classification (every car,
                 with grid, status/DNF, points, playoff points, laps) plus
                 the per-stage top-10 (the feed carries real stage results);
  * qualifying — per round whose pole-qualifying run has been published
                 (incl. the upcoming round, pre-race — the post-quali seam);
  * entries    — the upcoming round's pre-race entry list when the feed
                 already serves it;
  * driverStandings / teamStandings / manufacturerStandings — derived by
                 summing the feed's per-race ``points_earned`` (stage points
                 included), since the cacher's standings endpoints 403.

Guards (both root-caused from real incidents elsewhere in the monorepo):
  * wrong-event — every weekend feed is cross-checked against the
    human-verified config calendar (race_id + date + track) before ingestion;
    a mismatch raises ``WrongEventError`` before ``main()`` ever writes;
  * empty-scrape regression — a refresh that would REDUCE the committed
    snapshot's completed-round count refuses to write (a transient empty
    response must never wipe real data).

Run:  PYTHONPATH=src python -m nascar_predictions.refresh
          [--season 2026] [--out data/official_2026.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .sources.nascar_feed_source import NascarCacherClient, NascarFeedSource, WrongEventError

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_CACHE = _DATA_DIR / "api_cache"


def _default_out(season: int) -> Path:
    return _DATA_DIR / f"official_{season}.json"


def _stage_points_of(stages: dict[str, list[dict]], code: str) -> float:
    return sum(
        float(r.get("points") or 0.0)
        for rows in (stages or {}).values()
        for r in rows
        if r.get("code") == code
    )


def build_snapshot(season: int, *, source: NascarFeedSource | None = None) -> dict:
    # No disk cache here: refresh must see the LIVE state of every round (a
    # cached future-round feed would freeze qualifying/entries forever). The
    # bulk archive pull (backfill --history) is the cached path.
    src = source or NascarFeedSource(client=NascarCacherClient())
    races = src.season_races(season)
    if races is None:
        raise RuntimeError("NASCAR race list unavailable — refusing to build a snapshot")

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
    entries: dict[str, list[str]] = {}
    completed: list[int] = []
    for rnd in range(1, len(races) + 1):
        # Wrong-event guard: the source verifies each weekend feed against the
        # race list AND the config calendar (race_id + date + track) and
        # raises WrongEventError on a mismatch — a wrong event can never
        # mutate the committed snapshot.
        quali = src.qualifying(season, rnd)
        if quali:
            qualifying[str(rnd)] = quali
        rows = src.race_rows(season, rnd)
        if not rows:
            entry = src.entry_list(season, rnd)
            if entry:
                entries[str(rnd)] = entry
            continue  # round not yet run
        completed.append(rnd)
        block: dict = {"race": rows, "raceId": races[rnd - 1].get("race_id")}
        stages = src.stage_results(season, rnd)
        if stages:
            block["stages"] = stages
        results[str(rnd)] = block
        # Roster drift check: warn loudly on codes config knows nothing about
        # (a new entry needs a roster / PART_TIME_DRIVERS addition).
        for r in rows:
            if (
                season == config.SEASON
                and r["code"] not in config.TEAM_OF
                and r["code"] not in config.PART_TIME_DRIVERS
            ):
                print(
                    f"⚠️  round {rnd}: unknown driver code {r['code']} ({r['name']}) — "
                    "add the entry to config (roster / PART_TIME_DRIVERS)."
                )

    # ---- standings derived from the captured results (feeds' standings
    # endpoints are gated, but points_earned per row includes stage points,
    # so summing reproduces the official table) --------------------------- #
    drivers: dict[str, dict] = {}
    history: dict[str, list[float]] = {}
    for rnd in completed:
        for r in results[str(rnd)]["race"]:
            c = r["code"]
            d = drivers.setdefault(
                c,
                {
                    "code": c,
                    "name": r["name"],
                    "team": r["team"],
                    "make": r.get("make", ""),
                    "points": 0.0,
                    "wins": 0,
                    "podiums": 0,
                    "top10s": 0,
                    "stageWins": 0,
                    "playoffPoints": 0.0,
                    "lapsLed": 0,
                },
            )
            d["name"], d["team"], d["make"] = r["name"], r["team"], r.get("make", "")
            d["points"] += float(r.get("points") or 0.0)
            d["playoffPoints"] += float(r.get("playoffPoints") or 0.0)
            d["lapsLed"] += int(r.get("lapsLed") or 0)
            pos = r.get("position") or 0
            d["wins"] += 1 if pos == 1 else 0
            d["podiums"] += 1 if 0 < pos <= 3 else 0
            d["top10s"] += 1 if 0 < pos <= 10 else 0
        for stage_rows in (results[str(rnd)].get("stages") or {}).values():
            for s in stage_rows:
                if s.get("position") == 1 and s["code"] in drivers:
                    drivers[s["code"]]["stageWins"] += 1
        for c in drivers:
            history.setdefault(c, []).append(drivers[c]["points"])

    driver_rows = sorted(
        drivers.values(), key=lambda d: (-d["points"], -d["wins"], d["code"])
    )
    for i, d in enumerate(driver_rows, start=1):
        d["position"] = i
        # Pad the history for drivers who joined mid-season.
        h = history.get(d["code"], [])
        d["pointsHistory"] = [0.0] * (len(completed) - len(h)) + h

    def _group_rows(group_key: str) -> list[dict]:
        groups: dict[str, dict] = {}
        for rnd in completed:
            for r in results[str(rnd)]["race"]:
                g = r.get(group_key) or ""
                if not g:
                    continue
                row = groups.setdefault(g, {"points": 0.0, "wins": 0})
                row["points"] += float(r.get("points") or 0.0)
                row["wins"] += 1 if r.get("position") == 1 else 0
        ordered = sorted(groups.items(), key=lambda kv: (-kv[1]["points"], kv[0]))
        return [
            {"position": i, group_key: g, "points": v["points"], "wins": v["wins"]}
            for i, (g, v) in enumerate(ordered, start=1)
        ]

    team_rows = _group_rows("team")
    make_rows = _group_rows("make")

    calendar = []
    for i, meta in sorted(config.CALENDAR_META.items()):
        calendar.append(
            {
                "round": i,
                "key": meta["key"],
                "track": meta["track"],
                "raceName": meta["raceName"],
                "country": "United States",
                "kind": meta["kind"],
                "trackType": meta["trackType"],
                "date": meta["date"],
                "stageLaps": list(meta.get("stageLaps") or []),
                "completed": i in completed,
                "raceId": meta.get("raceId"),
            }
        )

    return {
        "season": season,
        "source": "cf.nascar.com",
        "series": config.CUP_SERIES_ID,
        "completedRounds": len(completed),
        "totalRounds": len(config.CALENDAR),
        "calendar": calendar,
        "driverStandings": driver_rows,
        "teamStandings": [
            {"position": t["position"], "team": t["team"], "points": t["points"], "wins": t["wins"]}
            for t in team_rows
        ],
        "manufacturerStandings": [
            {"position": m["position"], "make": m["make"], "points": m["points"], "wins": m["wins"]}
            for m in make_rows
        ],
        "results": results,
        "qualifying": qualifying,
        "entries": entries,
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
        description="Refresh the NASCAR real-data snapshot from the cf.nascar.com feeds"
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
    # ever add rounds, not lose them.
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

    # Reconciliation report: official (summed) totals vs table-derived points.
    # The feed's ``points_earned`` is authoritative — Cup points-eligibility
    # declarations (entries pointing in another series earn 0, with partial
    # shift-up effects verified in the 2026 feed) make exact table
    # reproduction impossible from outside. The check is therefore a DRIFT
    # gate: position-table + captured stage points must land within ~1 point
    # per 4 races of the official total; a real scoring-table or
    # stage-capture bug drifts an order of magnitude faster.
    table = config.RACE_POINTS_2026 if args.season >= 2026 else config.RACE_POINTS_2017_2025
    tolerance = max(2.0, 0.25 * snap["completedRounds"])
    ok = True
    for d in snap["driverStandings"][:5]:
        derived = 0.0
        for rnd_str, block in snap["results"].items():
            stages = block.get("stages") or {}
            for r in block["race"]:
                if r["code"] != d["code"]:
                    continue
                pos = r.get("position") or 0
                derived += float(table.get(pos, 1)) + _stage_points_of(stages, d["code"])
        flag = "" if abs(derived - d["points"]) <= tolerance else "  <-- MISMATCH"
        ok = ok and not flag
        print(f"  {d['position']:>2} {d['code']:<14} {d['points']:.0f} pts (Σtable={derived:.0f}){flag}")
    print(
        f"Wrote {out} — {snap['completedRounds']}/{snap['totalRounds']} rounds, "
        f"{len(snap['driverStandings'])} drivers, {len(snap['qualifying'])} qualifying "
        f"sessions, {len(snap['entries'])} entry list(s). reconciled={'yes' if ok else 'NO'}"
    )


if __name__ == "__main__":
    main()
