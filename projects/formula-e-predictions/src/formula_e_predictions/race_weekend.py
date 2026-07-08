"""FE race-weekend orchestration — the cheap freshness gate the cron polls.

The FE counterpart of the F1 flagship's ``gp_weekend.py`` / F3's
``race_weekend.py``. The race-weekend workflow polls across the Saturday/Sunday
windows; before it spins up the (heavier) live refresh + export it asks this
module two questions:

1. **Is this a race weekend right now?** (``is_race_weekend``) — a pure
   wall-clock check against the calendar, so off-weekend polls exit in
   milliseconds with no network. FE races are one-day events (qualifying and
   race share the morning/afternoon), and doubleheaders are two consecutive
   one-day rounds — each round gets its own window.
2. **Is there genuinely new data to publish?** (``check_work_pending``) — a
   single live probe of the Pulselive API compared against the committed
   snapshot: fresh qualifying the snapshot is missing (→ a post-quali forecast
   is due) or an official race result it does not yet have (→ post-race
   standings + the accuracy report are due). Only then does the workflow do
   real work.

The weekend **phase** (pre / post-quali / post-race) is derived from what data
is actually available — completion is data-driven, never a wall clock.

Run (used by the workflow):
    python -m formula_e_predictions.race_weekend --detect-round
    python -m formula_e_predictions.race_weekend --round N --is-race-weekend
    python -m formula_e_predictions.race_weekend --round N --check-work-pending
    python -m formula_e_predictions.race_weekend --round N --phase
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from . import config
from .sources.snapshot import load_snapshot

# How wide a window around a race day counts as "race weekend" for polling.
# FE runs qualifying + race on the same day; the pre-day covers shakedown/FP
# and the trailing days catch late-publishing results. The freshness gate
# still decides whether any work happens.
_PRE_DAYS = 1    # from the day before (covers FP + early qualifying posts)
_POST_DAYS = 2   # through two days after (covers a late-publishing result)


def _parse_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def weekend_window(round: int) -> tuple[datetime, datetime] | None:
    """(start, end) UTC datetimes bounding ``round``'s race window, or None."""
    meta = config.CALENDAR_META.get(round, {})
    race = _parse_date(meta.get("date", ""))
    if race is None:
        return None
    start = race - timedelta(days=_PRE_DAYS)
    end = race + timedelta(days=_POST_DAYS, hours=23, minutes=59)
    return start, end


def is_race_weekend(round: int, now: datetime | None = None) -> bool:
    """True when ``now`` falls within ``round``'s race-weekend window."""
    win = weekend_window(round)
    if win is None:
        return False
    now = now or _now()
    return win[0] <= now <= win[1]


def detect_target_round(year: int = config.SEASON, now: datetime | None = None) -> int:
    """The active round: the first whose window has not yet closed.

    Purely calendar-based so it is correct even when the committed snapshot is
    stale (the whole point of the freshness gate is to run *before*
    refreshing). Past the final round it pins to the last round.
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
    """A fresh Pulselive probe (no snapshot/synthetic fallback).

    Returns None when the client dependency is unavailable, so callers degrade
    to "no work pending" rather than crashing the gate.
    """
    try:
        from .sources.pulselive_source import PulseliveFESource

        return PulseliveFESource()
    except Exception:
        return None


def _snapshot_completed(snap: dict, round: int) -> bool:
    for c in snap.get("calendar", []):
        if c.get("round") == round:
            return bool(c.get("completed"))
    return False


def weekend_phase(round: int, year: int = config.SEASON, *, live=None) -> str:
    """'post-race' | 'post-quali' | 'pre' from whatever data is available.

    Prefers the live feed (freshest); falls back to the committed snapshot so
    the phase is still meaningful offline. Completion is data-driven, never
    wall-clock.
    """
    snap = load_snapshot(year)
    feature_live = quali_live = None
    if live is not None:
        try:
            feature_live = live.results(year, round)
            quali_live = live.qualifying(year, round)
        except Exception:
            feature_live, quali_live = None, None

    if feature_live or _snapshot_completed(snap, round):
        return "post-race"
    snap_quali = snap.get("qualifying", {}).get(str(round))
    if quali_live or snap_quali:
        return "post-quali"
    return "pre"


def stranded_rounds(year: int = config.SEASON, *, live=None, now: datetime | None = None) -> list[int]:
    """Completed rounds whose official result is missing from the snapshot.

    The FE counterpart of F1's stranded-results backfill: a round is stranded
    when its race date has passed, the committed snapshot does not list it as
    completed, and the live feed now carries the official result. This
    recovers a round whose result the feed did not yet have during its weekend
    window — without it, once ``detect_target_round`` has advanced, the missed
    result could never be picked up again.

    Cheap by construction: the wall-clock + snapshot candidate filter runs
    first with no network, and the live feed is only probed when a genuine
    candidate exists (normally none, or the single just-finished round).
    """
    now = now or _now()
    snap = load_snapshot(year)

    # ── Network-free pre-filter: past-race-date rounds not yet in the snapshot ──
    candidates = []
    for rnd in range(1, len(config.CALENDAR) + 1):
        race = _parse_date(config.CALENDAR_META.get(rnd, {}).get("date", ""))
        if race is None or now < race:
            continue  # race hasn't happened yet
        if _snapshot_completed(snap, rnd):
            continue  # already published
        candidates.append(rnd)
    if not candidates:
        return []

    # ── Only now (a candidate exists) touch the network to confirm. ──
    if live is None:
        live = _live_source()
    if live is None:
        return []

    stranded = []
    for rnd in candidates:
        try:
            if live.results(year, rnd):
                stranded.append(rnd)
        except Exception:
            continue
    return stranded


def check_work_pending(round: int, year: int = config.SEASON, *, live=None) -> bool:
    """Is there fresh live data the committed snapshot does not yet carry?

    Three kinds of pending work, mirroring F1's ``work_pending``:
      * post-race — the live feed has this round's official result but the
        snapshot does not list the round as completed;
      * post-quali — the live feed has this round's qualifying order and it
        differs from (or is absent in) the snapshot;
      * stranded — ANY prior completed round whose official result the
        snapshot is still missing but the live feed now carries.

    A live-probe failure (API down) yields False — the safety-net polls and
    the next interval retry, never a spurious heavy run.
    """
    if live is None:
        live = _live_source()
    if live is None:
        return False
    snap = load_snapshot(year)

    try:
        live_result = live.results(year, round)
    except Exception:
        live_result = None
    if live_result and not _snapshot_completed(snap, round):
        return True

    try:
        live_quali = live.qualifying(year, round)
    except Exception:
        live_quali = None
    if live_quali:
        snap_quali = snap.get("qualifying", {}).get(str(round))
        if list(live_quali) != list(snap_quali or []):
            return True

    # Recover any prior round stranded without its official result. Reuses the
    # same live probe so the sweep adds no extra source instantiation.
    if stranded_rounds(year, live=live):
        return True

    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="FE race-weekend freshness gate / phase detector")
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
    print(
        f"season={args.season} round={rnd} race_weekend={is_race_weekend(rnd)} "
        f"phase={weekend_phase(rnd, args.season)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
