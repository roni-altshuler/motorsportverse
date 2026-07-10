"""Refresh the committed IndyCar snapshot from Wikipedia — append-only, gated.

Snapshot-primary discipline: ``data/history_<season>.json`` is the SINGLE
source of truth for the active season (the same file family as the curated
archive seasons). This is the only module allowed to write it, and it can
only ever **append newly completed rounds** — behind ``--require-clean-parse``
semantics: ANY validation failure aborts with NO write. A refresh is a no-op
or a verified append, never a mutation of reviewed data.

Guards (all root-caused from real incidents elsewhere in the monorepo):

* **wrong-event** — the scraped season schedule is cross-checked against the
  human-verified config calendar round-for-round (venue + date + round count)
  and every race article must name the season year; a mismatch raises
  ``WrongEventError`` before anything is ingested.
* **clean-parse** — every classification must pass the car-count band, the
  contiguous-positions check, the awarded-points requirement and the roster
  whitelist (``DirtyParseError`` otherwise). Truncated tables, schedule pages
  mis-read as results, or another series' page are refused wholesale.
* **history immutability** — rounds already in the committed file must parse
  to the SAME race (winner + classified car count fingerprint); a mismatch
  refuses the whole refresh (a retro-edit needs human review, not a cron).
* **standings verification** — the appended file's per-race awarded points
  are re-summed and checked against the season page's official standings grid
  (champion + top-5 order must match, the curation pipeline's own gate).
* **no-regression** — the file can only gain rounds, never lose them.

Run:  PYTHONPATH=src python -m indycar_predictions.refresh
          [--season 2026] [--out data/history_2026.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from . import config
from .sources.indycar_scraper_source import (
    DirtyParseError,
    IndycarScraperSource,
    WrongEventError,
)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _default_out(season: int) -> Path:
    base = config._DATA_DIR if config._DATA_DIR.exists() else _DATA_DIR
    return base / f"history_{season}.json"


def _calendar_path(season: int) -> Path:
    base = config._DATA_DIR if config._DATA_DIR.exists() else _DATA_DIR
    return base / f"calendar_{season}.json"


def _fingerprint(results: list[dict]) -> tuple[str | None, int]:
    """(winner, classified car count) — the immutability check for a round."""
    winner = next((r.get("driver") for r in results if r.get("position") == 1), None)
    n = sum(1 for r in results if r.get("position") is not None)
    return winner, n


def _round_meta(season: int, rnd: int) -> dict:
    meta = config.CALENDAR_META.get(rnd, {})
    return {
        "round": rnd,
        "name": meta.get("raceName"),
        "venue": meta.get("venue"),
        "venue_key": meta.get("key"),
        "date": meta.get("date"),
        "track_type": meta.get("trackType"),
        "has_full_detail": True,
    }


def _verify_standings(snapshot: dict, official: list[dict]) -> dict:
    """Curation-style verification: recompute the top-5 by summing the file's
    awarded per-race points and compare to the official standings grid."""
    curated: dict[str, float] = {}
    for rd in snapshot["rounds"]:
        for r in rd["results"]:
            if r.get("points") is not None:
                curated[r["driver"]] = curated.get(r["driver"], 0.0) + float(r["points"])
    mismatches = []
    for s in official:
        c = curated.get(s["driver"], 0.0)
        o = s.get("points")
        if o is None:
            continue
        if abs(c - o) > 0.5:
            mismatches.append(
                {"driver": s["driver"], "curated": c, "official": o, "diff": c - o}
            )
    top5_official = [s["driver"] for s in official[:5]]
    recomputed = sorted(curated.items(), key=lambda kv: -kv[1])
    top5_recomputed = [d for d, _ in recomputed[:5]]
    return {
        "method": "point-sum-recompute",
        "detail_complete": all(rd.get("has_full_detail") for rd in snapshot["rounds"]),
        "rounds_with_full_detail": sum(
            1 for rd in snapshot["rounds"] if rd.get("has_full_detail")
        ),
        "official_champion": top5_official[0] if top5_official else None,
        "recomputed_champion": top5_recomputed[0] if top5_recomputed else None,
        "champion_match": bool(top5_official)
        and bool(top5_recomputed)
        and top5_official[0] == top5_recomputed[0],
        "top5_official": top5_official,
        "top5_recomputed": top5_recomputed,
        "top5_match": top5_official == top5_recomputed,
        "point_mismatches": mismatches,
        "n_mismatches": len(mismatches),
    }


def build_refreshed_snapshot(
    season: int,
    existing: dict,
    *,
    source: IndycarScraperSource | None = None,
) -> tuple[dict, list[int]]:
    """The existing snapshot plus any newly completed, fully validated rounds.

    Returns ``(snapshot, appended_round_numbers)``. Raises ``WrongEventError``
    / ``DirtyParseError`` / ``RuntimeError`` on ANY problem — the caller
    writes nothing in that case (``--require-clean-parse`` semantics).
    """
    if int(existing.get("season", 0)) != season:
        raise RuntimeError(
            f"data/history_{season}.json is missing or not for season {season} — "
            "refresh only ever appends to the committed snapshot"
        )
    src = source or IndycarScraperSource()
    state = src.season_state(season)
    if state is None:
        raise RuntimeError(
            "season page unavailable/unparseable — refusing to build a snapshot"
        )
    if not state["clean"]:
        raise DirtyParseError(
            "season parse is not clean — " + "; ".join(state["notes"])
        )

    existing_rounds = {int(rd["round"]): rd for rd in existing.get("rounds", [])}
    n_existing = len(existing_rounds)

    # ---- history immutability: every committed round must re-parse to the
    # same race (winner + classified count fingerprint) ---------------------- #
    for rnd, rd in sorted(existing_rounds.items()):
        fresh = src.raw_results(season, rnd)
        if fresh is None:
            raise DirtyParseError(
                f"round {rnd}: committed round no longer parses cleanly — refusing"
            )
        if _fingerprint(fresh) != _fingerprint(rd.get("results", [])):
            raise WrongEventError(
                f"round {rnd}: fresh parse disagrees with the committed snapshot "
                f"(fingerprint {_fingerprint(fresh)} vs "
                f"{_fingerprint(rd.get('results', []))}) — a retro-edit needs human review"
            )

    # ---- append newly completed rounds, contiguous from the snapshot ------- #
    appended: list[int] = []
    rounds = [existing_rounds[r] for r in sorted(existing_rounds)]
    for rnd in range(n_existing + 1, len(config.CALENDAR_META) + 1):
        fresh = src.raw_results(season, rnd)  # validates or raises
        if fresh is None:
            break  # next round not run yet — completion is contiguous
        entry = _round_meta(season, rnd)
        entry["results"] = fresh
        rounds.append(entry)
        appended.append(rnd)

    snapshot = dict(existing)
    snapshot["rounds"] = rounds
    snapshot["rounds_curated"] = len(rounds)
    snapshot["generated"] = date.today().isoformat()
    snapshot["track_types"] = {
        t: sum(1 for rd in rounds if rd.get("track_type") == t)
        for t in config.TRACK_TYPES
    }
    snapshot["winners"] = [
        {
            "round": rd["round"],
            "name": rd.get("name"),
            "venue": rd.get("venue"),
            "is_indy500": config.is_indy500_round(int(rd["round"])),
            "winner": next(
                (r["driver"] for r in rd["results"] if r.get("position") == 1), None
            ),
        }
        for rd in rounds
    ]

    # ---- standings: the season page's official grid + verification --------- #
    official = state["standings"]
    if not official:
        raise DirtyParseError("season page standings grid did not parse — refusing")
    snapshot["final_standings"] = official
    verification = _verify_standings(snapshot, official)
    if not (verification["champion_match"] and verification["top5_match"]):
        raise DirtyParseError(
            "standings verification failed (champion/top-5 mismatch between the "
            f"summed per-race points and the official grid): {verification}"
        )
    snapshot["verification"] = verification

    notes = [n for n in snapshot.get("notes", []) if not n.startswith("IN-PROGRESS")]
    total = len(config.CALENDAR_META)
    if len(rounds) < total:
        notes.append(
            f"IN-PROGRESS season: {len(rounds)} of {total} rounds completed and curated"
        )
    if appended:
        notes.append(
            f"refresh {date.today().isoformat()}: appended round(s) "
            f"{', '.join(map(str, appended))} from the live Wikipedia parse"
        )
    snapshot["notes"] = notes
    return snapshot, appended


def update_calendar_file(season: int, completed: int, *, path: Path | None = None) -> None:
    """Sync the committed calendar file's completed flags with the snapshot."""
    p = path or _calendar_path(season)
    payload = json.loads(p.read_text(encoding="utf-8"))
    for entry in payload.get("calendar", []):
        entry["completed"] = int(entry.get("round", 0)) <= completed
    payload["completed_rounds"] = completed
    payload["remaining_rounds"] = max(0, int(payload.get("total_rounds", 0)) - completed)
    payload["generated"] = date.today().isoformat()
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Refresh the committed IndyCar snapshot from Wikipedia (append-only)"
    )
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument(
        "--require-clean-parse",
        action="store_true",
        default=True,
        help="refuse to write on ANY validation failure (always on — the flag "
        "exists for CLI self-documentation; there is no bypass)",
    )
    args = ap.parse_args()
    out = args.out or _default_out(args.season)

    try:
        existing = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        existing = {}

    try:
        snapshot, appended = build_refreshed_snapshot(args.season, existing)
    except (WrongEventError, DirtyParseError, RuntimeError) as exc:
        print(f"refresh: REFUSED — {exc}", flush=True)
        return 1

    # No-regression guard (structural: we only append, but belt-and-braces).
    if len(snapshot["rounds"]) < len(existing.get("rounds", [])):
        print("refresh: REFUSED — refresh would lose committed rounds", flush=True)
        return 1

    if not appended:
        print(
            f"refresh: no new rounds ({len(snapshot['rounds'])}/"
            f"{len(config.CALENDAR_META)} completed) — snapshot unchanged"
        )
        return 0
    if args.dry_run:
        print(f"refresh: [dry-run] would append round(s) {appended} to {out}")
        return 0

    out.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    try:
        update_calendar_file(args.season, len(snapshot["rounds"]))
    except Exception as exc:  # calendar sync is best-effort; the snapshot is canonical
        print(f"refresh: warning — calendar file not updated ({exc})")
    v = snapshot["verification"]
    print(
        f"refresh: appended round(s) {appended} → {out} "
        f"({len(snapshot['rounds'])}/{len(config.CALENDAR_META)} rounds; "
        f"champion check {'PASS' if v['champion_match'] else 'FAIL'}, "
        f"{v['n_mismatches']} point residual(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
