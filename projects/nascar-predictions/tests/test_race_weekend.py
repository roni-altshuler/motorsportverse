"""Race-weekend gate: windows, round detection, phases, freshness checks."""
from __future__ import annotations

from datetime import datetime, timezone

from nascar_predictions import config, race_weekend as rw

SEASON = config.SEASON


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Wall-clock window logic (no network)
# --------------------------------------------------------------------------- #
def test_weekend_window_brackets_race_day():
    win = rw.weekend_window(20)  # Atlanta, 2026-07-12 (Sunday)
    assert win is not None
    start, end = win
    assert start.date().isoformat() == "2026-07-10"
    assert end.date().isoformat() == "2026-07-14"


def test_is_race_weekend():
    assert rw.is_race_weekend(20, now=_dt("2026-07-12 18:00"))
    assert rw.is_race_weekend(20, now=_dt("2026-07-11 12:00"))   # quali day
    assert not rw.is_race_weekend(20, now=_dt("2026-07-08 12:00"))
    assert not rw.is_race_weekend(20, now=_dt("2026-07-16 12:00"))


def test_detect_target_round_walks_the_calendar():
    assert rw.detect_target_round(SEASON, now=_dt("2026-02-01 00:00")) == 1
    # Between Chicagoland (r19, 07-05) and Atlanta (r20, 07-12): target 20.
    assert rw.detect_target_round(SEASON, now=_dt("2026-07-08 12:00")) == 20
    # Past the finale it pins to the last round.
    assert rw.detect_target_round(SEASON, now=_dt("2026-11-20 00:00")) == 36


# --------------------------------------------------------------------------- #
# Phase (data-driven; offline snapshot)
# --------------------------------------------------------------------------- #
def test_phase_post_race_for_completed_round():
    assert rw.weekend_phase(19, SEASON) == "post-race"


def test_phase_pre_for_upcoming_round():
    # Round 21's qualifying has not run and no result exists.
    assert rw.weekend_phase(21, SEASON) == "pre"


class _FakeLive:
    def __init__(self, results_by_round=None, quali_by_round=None):
        self._results = results_by_round or {}
        self._quali = quali_by_round or {}

    def results(self, year, rnd, race_index: int = 0):
        return self._results.get(rnd)

    def qualifying(self, year, rnd):
        return self._quali.get(rnd)


def test_phase_post_quali_from_live_feed():
    live = _FakeLive(quali_by_round={20: ["DEHAMLIN", "KYLARSON"]})
    assert rw.weekend_phase(20, SEASON, live=live) == "post-quali"


# --------------------------------------------------------------------------- #
# Freshness gate
# --------------------------------------------------------------------------- #
def test_no_work_when_live_matches_snapshot():
    live = _FakeLive()
    assert rw.check_work_pending(20, SEASON, live=live) is False


def test_work_pending_on_fresh_result():
    live = _FakeLive(results_by_round={20: ["r"]})
    assert rw.check_work_pending(20, SEASON, live=live) is True


def test_work_pending_on_fresh_quali():
    live = _FakeLive(quali_by_round={20: ["DEHAMLIN", "KYLARSON", "WIBYRON"]})
    assert rw.check_work_pending(20, SEASON, live=live) is True


def test_no_work_when_quali_already_snapshotted():
    """A quali order identical to the snapshot's is not fresh work."""
    from nascar_predictions.sources.snapshot import load_snapshot

    snap = load_snapshot(SEASON)
    rnd = max(int(k) for k in snap.get("qualifying", {}))
    live = _FakeLive(quali_by_round={rnd: list(snap["qualifying"][str(rnd)])})
    assert rw.check_work_pending(rnd, SEASON, live=live) is False


def test_stranded_round_recovery(monkeypatch):
    """A past-date round missing from the snapshot but present live = stranded."""
    live = _FakeLive(results_by_round={20: ["r"]})
    now = _dt("2026-07-15 12:00")  # after Atlanta
    assert rw.stranded_rounds(SEASON, live=live, now=now) == [20]
    # And the sweep surfaces it as pending work even when polling round 21.
    monkeypatch.setattr(rw, "_now", lambda: now)
    assert rw.check_work_pending(21, SEASON, live=live) is True


def test_stranded_rounds_empty_before_race_dates():
    live = _FakeLive(results_by_round={20: ["r"]})
    assert rw.stranded_rounds(SEASON, live=live, now=_dt("2026-07-09 00:00")) == []
