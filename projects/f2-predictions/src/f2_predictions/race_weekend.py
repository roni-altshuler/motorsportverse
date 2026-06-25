"""F2 race-weekend orchestration — the cheap freshness gate the cron polls.

This is the F2 counterpart of the F1 flagship's ``gp_weekend.py``. The race-weekend
workflow polls every 15 minutes across the Saturday/Sunday windows; before it spins
up the (heavier) live refresh + export it asks this module two questions:

1. **Is this a race weekend right now?** (``is_race_weekend``) — a pure wall-clock
   check against the calendar, so off-weekend polls exit in milliseconds with no
   network.
2. **Is there genuinely new data to publish?** (``check_work_pending``) — a single
   live probe of fiaformula2.com compared against the committed snapshot: fresh
   qualifying the snapshot is missing (→ a post-quali forecast is due) or an
   official race result it does not yet have (→ post-race standings + the model-vs-
   actual accuracy report are due). Only then does the workflow do real work.

This keeps the tight Sat/Sun polling cheap while cutting result latency from a
week (the old Monday-only refresh) to within one poll interval — matching F1.

The weekend **phase** (pre / post-quali / post-race) is derived from what data is
actually available, exactly like F1: completion is data-driven, never a wall clock.

Run (used by the workflow):
    python -m f2_predictions.race_weekend --detect-round
    python -m f2_predictions.race_weekend --round N --is-race-weekend
    python -m f2_predictions.race_weekend --round N --check-work-pending
    python -m f2_predictions.race_weekend --round N --phase
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import config
from .sources.snapshot import load_snapshot

# How wide a window around the weekend counts as "race weekend" for polling. F2
# qualifying is Friday (sprint Saturday, feature Sunday); the generous margins let
# the Friday quali poll and the Monday/Tuesday post-race safety net both fall
# inside the window. The freshness gate still decides whether any work happens.
_PRE_DAYS = 2    # from Thursday (covers Friday qualifying)
_POST_DAYS = 2   # through Tuesday (covers a late-publishing result)


def _parse_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def weekend_window(round: int) -> tuple[datetime, datetime] | None:
    """(start, end) UTC datetimes bounding ``round``'s race weekend, or None."""
    meta = config.CALENDAR_META.get(round, {})
    sprint = _parse_date(meta.get("sprint", ""))
    feature = _parse_date(meta.get("feature", "")) or sprint
    if sprint is None or feature is None:
        return None
    start = sprint - timedelta(days=_PRE_DAYS)
    end = feature + timedelta(days=_POST_DAYS, hours=23, minutes=59)
    return start, end


def is_race_weekend(round: int, now: datetime | None = None) -> bool:
    """True when ``now`` falls within ``round``'s race-weekend window."""
    win = weekend_window(round)
    if win is None:
        return False
    now = now or _now()
    return win[0] <= now <= win[1]


def detect_target_round(year: int = config.SEASON, now: datetime | None = None) -> int:
    """The active round: the first whose weekend window has not yet closed.

    Purely calendar-based so it is correct even when the committed snapshot is
    stale (the whole point of the freshness gate is to run *before* refreshing).
    Past the final round it pins to the last round.
    """
    now = now or _now()
    n = len(config.CALENDAR)
    for rnd in range(1, n + 1):
        win = weekend_window(rnd)
        if win is None:
            continue
        if now <= win[1]:
            return rnd
    return n


def _live_source():
    """A fresh fiaformula2.com probe (no snapshot/synthetic fallback).

    Returns None when the scraper dependency or season anchor is unavailable, so
    callers degrade to "no work pending" rather than crashing the gate.
    """
    try:
        from .sources.fia_f2_source import FiaF2Source

        return FiaF2Source()
    except Exception:
        return None


def _snapshot_completed(snap: dict, round: int) -> bool:
    for c in snap.get("calendar", []):
        if c.get("round") == round:
            return bool(c.get("completed"))
    return False


def weekend_phase(round: int, year: int = config.SEASON, *, live=None) -> str:
    """'post-race' | 'post-quali' | 'pre' from whatever data is available.

    Prefers the live feed (freshest); falls back to the committed snapshot so the
    phase is still meaningful offline. Completion is data-driven, never wall-clock.
    """
    snap = load_snapshot()
    feature_live = quali_live = None
    if live is not None:
        try:
            feature_live = live.results(year, round, race_index=1)
            quali_live = live.qualifying(year, round)
        except Exception:
            feature_live, quali_live = None, None

    if feature_live or _snapshot_completed(snap, round):
        return "post-race"
    snap_quali = snap.get("qualifying", {}).get(str(round))
    if quali_live or snap_quali:
        return "post-quali"
    return "pre"


def check_work_pending(round: int, year: int = config.SEASON, *, live=None) -> bool:
    """Is there fresh live data the committed snapshot does not yet carry?

    Two kinds of pending work, mirroring F1's quali/race phases:
      * post-race — the live feed has this round's official feature result but the
        snapshot does not list the round as completed;
      * post-quali — the live feed has this round's qualifying order and it differs
        from (or is absent in) the snapshot.

    A live-probe failure (site down, anchor missing) yields False — the safety-net
    polls and the next interval retry, never a spurious heavy run.
    """
    if live is None:
        live = _live_source()
    if live is None:
        return False
    snap = load_snapshot()

    try:
        live_feature = live.results(year, round, race_index=1)
    except Exception:
        live_feature = None
    if live_feature and not _snapshot_completed(snap, round):
        return True

    try:
        live_quali = live.qualifying(year, round)
    except Exception:
        live_quali = None
    if live_quali:
        snap_quali = snap.get("qualifying", {}).get(str(round))
        if list(live_quali) != list(snap_quali or []):
            return True

    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="F2 race-weekend freshness gate / phase detector")
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--round", type=int, default=None)
    ap.add_argument("--detect-round", action="store_true", help="print the active round and exit")
    ap.add_argument("--is-race-weekend", action="store_true", help="print true/false for --round")
    ap.add_argument("--phase", action="store_true", help="print pre/post-quali/post-race for --round")
    ap.add_argument(
        "--check-work-pending",
        action="store_true",
        help="print yes/no — is there fresh live data the snapshot is missing for --round",
    )
    args = ap.parse_args()

    rnd = args.round or detect_target_round(args.season)

    if args.detect_round:
        print(rnd)
        return 0
    if args.is_race_weekend:
        print("true" if is_race_weekend(rnd) else "false")
        return 0
    if args.phase:
        live = _live_source()
        print(weekend_phase(rnd, args.season, live=live))
        return 0
    if args.check_work_pending:
        print("yes" if check_work_pending(rnd, args.season) else "no")
        return 0

    # Default: a human-readable summary.
    print(f"season={args.season} round={rnd} race_weekend={is_race_weekend(rnd)} phase={weekend_phase(rnd, args.season)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
