"""Race-weekend gate: windows, round detection, phases, freshness checks."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from formula_e_predictions import config, race_weekend as rw

SEASON = config.SEASON
# The first round the committed snapshot does not yet carry (F3-parity).
# Derived, never hardcoded: a literal "next round" fails the suite the moment
# the race-weekend cron commits that round's result to official_<season>.json.
NEXT = config.COMPLETED_ROUNDS + 1


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _pinned_snapshot(completed_upto: int) -> dict:
    """A synthetic snapshot fixed at ``completed_upto`` rounds, for tests whose
    scenario must hold no matter how far the committed season has advanced."""
    return {
        "season": SEASON,
        "calendar": [
            {"round": r, "completed": r <= completed_upto}
            for r in range(1, len(config.CALENDAR) + 1)
        ],
        "results": {},
        "qualifying": {},
    }


# --------------------------------------------------------------------------- #
# Wall-clock window logic (no network)
# --------------------------------------------------------------------------- #
def test_weekend_window_brackets_race_day():
    win = rw.weekend_window(14)  # Tokyo, 2026-07-25
    assert win is not None
    start, end = win
    assert start.date().isoformat() == "2026-07-24"
    assert end.date().isoformat() == "2026-07-27"


def test_is_race_weekend():
    assert rw.is_race_weekend(14, now=_dt("2026-07-25 09:00"))
    assert rw.is_race_weekend(14, now=_dt("2026-07-24 12:00"))   # day before
    assert not rw.is_race_weekend(14, now=_dt("2026-07-20 12:00"))
    assert not rw.is_race_weekend(14, now=_dt("2026-08-01 12:00"))


def test_detect_target_round_walks_the_calendar():
    assert rw.detect_target_round(SEASON, now=_dt("2025-12-01 00:00")) == 1
    # Between Shanghai (r13, 07-05 + post window) and Tokyo (r14): target is 14.
    assert rw.detect_target_round(SEASON, now=_dt("2026-07-10 00:00")) == 14
    # Doubleheader: the day after Tokyo race 1 belongs to round 14's window,
    # but round 14 is detected until ITS window closes.
    assert rw.detect_target_round(SEASON, now=_dt("2026-07-26 08:00")) == 14
    # Past the finale it pins to the last round.
    assert rw.detect_target_round(SEASON, now=_dt("2026-09-15 00:00")) == 17


# --------------------------------------------------------------------------- #
# Phase (data-driven; offline snapshot)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(config.COMPLETED_ROUNDS == 0, reason="fresh season: nothing completed yet")
def test_phase_post_race_for_completed_round():
    assert rw.weekend_phase(config.COMPLETED_ROUNDS, SEASON) == "post-race"


def test_phase_pre_for_upcoming_round(monkeypatch):
    # Hermetic: "pre" must hold when neither the live feed nor the snapshot
    # carries the round — pin an empty snapshot so a committed post-quali
    # weekend can't flip the assertion mid-weekend.
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(0))
    assert rw.weekend_phase(NEXT, SEASON) == "pre"


class _FakeLive:
    def __init__(self, results_by_round=None, quali_by_round=None):
        self._results = results_by_round or {}
        self._quali = quali_by_round or {}

    def results(self, year, rnd, race_index: int = 0):
        return self._results.get(rnd)

    def qualifying(self, year, rnd):
        return self._quali.get(rnd)


def test_phase_post_quali_from_live_feed():
    live = _FakeLive(quali_by_round={NEXT: ["EVA", "WEH"]})
    assert rw.weekend_phase(NEXT, SEASON, live=live) == "post-quali"


# --------------------------------------------------------------------------- #
# Freshness gate
# --------------------------------------------------------------------------- #
def test_no_work_when_live_matches_snapshot():
    live = _FakeLive()
    assert rw.check_work_pending(NEXT, SEASON, live=live) is False


def test_work_pending_on_fresh_result():
    live = _FakeLive(results_by_round={NEXT: ["r"]})
    assert rw.check_work_pending(NEXT, SEASON, live=live) is True


def test_work_pending_on_fresh_quali():
    live = _FakeLive(quali_by_round={NEXT: ["EVA", "WEH", "ROW"]})
    assert rw.check_work_pending(NEXT, SEASON, live=live) is True


def test_no_work_when_quali_already_snapshotted():
    """A quali order identical to the snapshot's is not fresh work."""
    from formula_e_predictions.sources.snapshot import load_snapshot

    snap = load_snapshot(SEASON)
    rnd = max(int(k) for k in snap.get("qualifying", {}))
    live = _FakeLive(quali_by_round={rnd: list(snap["qualifying"][str(rnd)])})
    # The round is completed in the snapshot, so no post-race work either.
    assert rw.check_work_pending(rnd, SEASON, live=live) is False


def test_stranded_round_recovery(monkeypatch):
    """A past-date round missing from the snapshot but present live = stranded."""
    # Pin the snapshot at 13 completed rounds: the Tokyo (r14) scenario is
    # built on static calendar dates and must survive the real snapshot
    # advancing past it.
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(13))
    live = _FakeLive(results_by_round={14: ["r"]})
    now = _dt("2026-07-27 12:00")  # after Tokyo race 1
    assert rw.stranded_rounds(SEASON, live=live, now=now) == [14]
    # And the sweep surfaces it as pending work even when polling round 15.
    monkeypatch.setattr(rw, "_now", lambda: now)
    assert rw.check_work_pending(15, SEASON, live=live) is True


def test_stranded_rounds_empty_before_race_dates(monkeypatch):
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(13))
    live = _FakeLive(results_by_round={14: ["r"]})
    assert rw.stranded_rounds(SEASON, live=live, now=_dt("2026-07-20 00:00")) == []
