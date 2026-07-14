"""Race-weekend gate: windows (incl. the Indy 500 May build-up), round
detection, phases, freshness checks."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from indycar_predictions import config, race_weekend as rw

SEASON = config.SEASON
# The first round the committed snapshot does not yet carry (F3-parity).
# Derived, never hardcoded: a literal "next round" fails the suite the moment
# the race-weekend cron commits that round's result to the snapshot.
NEXT = config.COMPLETED_ROUNDS + 1


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _pinned_snapshot(completed_upto: int) -> dict:
    """A synthetic snapshot fixed at ``completed_upto`` rounds, for tests whose
    scenario must hold no matter how far the committed season has advanced."""
    return {
        "season": SEASON,
        "rounds": [{"round": r} for r in range(1, completed_upto + 1)],
        "qualifying": {},
    }


# --------------------------------------------------------------------------- #
# Wall-clock window logic (no network)
# --------------------------------------------------------------------------- #
def test_weekend_window_brackets_race_day():
    win = rw.weekend_window(12)  # Nashville, 2026-07-19 (Sunday)
    assert win is not None
    start, end = win
    assert start.date().isoformat() == "2026-07-17"
    assert end.date().isoformat() == "2026-07-21"


def test_indy500_window_opens_for_the_qualifying_weekend():
    """The 500 (2026-05-24) qualifies the weekend before — the window must
    open ~9 days out, unlike a normal round's 2."""
    win = rw.weekend_window(7)
    assert win is not None
    assert win[0].date().isoformat() == "2026-05-15"
    assert rw.is_race_weekend(7, now=_dt("2026-05-16 12:00"))   # quali weekend
    # A normal round is NOT in-window nine days out.
    assert not rw.is_race_weekend(12, now=_dt("2026-07-10 12:00"))


def test_is_race_weekend():
    assert rw.is_race_weekend(12, now=_dt("2026-07-19 18:00"))
    assert rw.is_race_weekend(12, now=_dt("2026-07-18 12:00"))   # quali day
    assert not rw.is_race_weekend(12, now=_dt("2026-07-08 12:00"))
    assert not rw.is_race_weekend(12, now=_dt("2026-07-25 12:00"))


def test_detect_target_round_walks_the_calendar():
    assert rw.detect_target_round(SEASON, now=_dt("2026-02-01 00:00")) == 1
    # Between Mid-Ohio (r11, 07-05) and Nashville (r12, 07-19): target 12.
    assert rw.detect_target_round(SEASON, now=_dt("2026-07-08 12:00")) == 12
    # The Milwaukee Saturday/Sunday double-header resolves in date order.
    assert rw.detect_target_round(SEASON, now=_dt("2026-08-29 23:00")) in (16, 17)
    # Past the finale it pins to the last round.
    assert rw.detect_target_round(SEASON, now=_dt("2026-10-20 00:00")) == 18


# --------------------------------------------------------------------------- #
# Phase (data-driven; offline snapshot)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(config.COMPLETED_ROUNDS == 0, reason="fresh season: nothing completed yet")
def test_phase_post_race_for_completed_round():
    assert rw.weekend_phase(config.COMPLETED_ROUNDS, SEASON) == "post-race"


def test_phase_pre_for_upcoming_round(monkeypatch):
    # Hermetic: "pre" must hold when neither the live probe nor the snapshot
    # carries the round — pin an empty snapshot so a committed qualifying
    # weekend can't flip the assertion mid-weekend.
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(0))
    assert rw.weekend_phase(NEXT, SEASON) == "pre"


class _FakeLive:
    def __init__(self, results_by_round=None):
        self._results = results_by_round or {}

    def results(self, year, rnd, race_index: int = 0):
        return self._results.get(rnd)


def test_phase_post_race_from_live_probe():
    live = _FakeLive(results_by_round={NEXT: ["r"]})
    assert rw.weekend_phase(NEXT, SEASON, live=live) == "post-race"


# --------------------------------------------------------------------------- #
# Freshness gate
# --------------------------------------------------------------------------- #
def test_no_work_when_live_matches_snapshot():
    assert rw.check_work_pending(NEXT, SEASON, live=_FakeLive()) is False


def test_work_pending_on_fresh_result():
    live = _FakeLive(results_by_round={NEXT: ["r"]})
    assert rw.check_work_pending(NEXT, SEASON, live=live) is True


@pytest.mark.skipif(config.COMPLETED_ROUNDS == 0, reason="fresh season: nothing completed yet")
def test_completed_round_is_not_fresh_work():
    """The latest completed round is already in the committed snapshot — a
    live result for it is not pending work."""
    live = _FakeLive(results_by_round={config.COMPLETED_ROUNDS: ["r"]})
    assert rw.check_work_pending(config.COMPLETED_ROUNDS, SEASON, live=live) is False


def test_stranded_round_recovery(monkeypatch):
    """A past-date round missing from the snapshot but present live = stranded."""
    # Pin the snapshot at 11 completed rounds: the Nashville (r12) scenario is
    # built on static calendar dates and must survive the real snapshot
    # advancing past it.
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(11))
    live = _FakeLive(results_by_round={12: ["r"]})
    now = _dt("2026-07-22 12:00")  # after Nashville
    assert rw.stranded_rounds(SEASON, live=live, now=now) == [12]
    # And the sweep surfaces it as pending work even when polling round 13.
    monkeypatch.setattr(rw, "_now", lambda: now)
    assert rw.check_work_pending(13, SEASON, live=live) is True


def test_stranded_rounds_empty_before_race_dates(monkeypatch):
    monkeypatch.setattr(rw, "load_snapshot", lambda *a, **k: _pinned_snapshot(11))
    live = _FakeLive(results_by_round={12: ["r"]})
    assert rw.stranded_rounds(SEASON, live=live, now=_dt("2026-07-10 00:00")) == []
