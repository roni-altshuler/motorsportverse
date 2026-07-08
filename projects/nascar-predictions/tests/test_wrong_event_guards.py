"""Wrong-event guards: a mismatched race can never be ingested as a round.

Root-caused from the F1 flagship's 2026-07-05 incident (FastF1 fuzzy-matched
Great Britain → Austria and published R8 results as R9 pre-race): every live
path verifies event identity before parsing anything.
"""
from __future__ import annotations

import copy

import pytest
from conftest import FakeCacherClient, load_fixture

from nascar_predictions import config
from nascar_predictions.sources.nascar_feed_source import (
    NascarFeedSource,
    WrongEventError,
    verify_race_identity,
)

SEASON = config.SEASON


def _race_meta(**over):
    base = {
        "race_id": 5596,
        "race_date": "2026-02-15T14:30:00",
        "track_name": "Daytona International Speedway",
        "race_name": "DAYTONA 500",
    }
    base.update(over)
    return base


def test_identity_ok():
    verify_race_identity(
        _race_meta(),
        round=1,
        expected={"raceId": 5596, "date": "2026-02-15", "track": "Daytona International Speedway"},
    )


def test_race_id_mismatch_raises():
    with pytest.raises(WrongEventError):
        verify_race_identity(_race_meta(), round=1, expected={"raceId": 5597})


def test_date_mismatch_raises():
    with pytest.raises(WrongEventError):
        verify_race_identity(_race_meta(), round=1, expected={"date": "2026-02-22"})


def test_date_tolerance_allows_rain_delay():
    """The race list carries the rescheduled date, the weekend feed the
    original (verified on the 2020 Daytona 500 Sunday→Monday delay)."""
    verify_race_identity(
        _race_meta(race_date="2026-02-16T14:30:00"),
        round=1,
        expected={"date": "2026-02-15"},
        date_tolerance_days=5,
    )
    with pytest.raises(WrongEventError):
        verify_race_identity(
            _race_meta(race_date="2026-03-15T14:30:00"),
            round=1,
            expected={"date": "2026-02-15"},
            date_tolerance_days=5,
        )


def test_track_mismatch_raises():
    with pytest.raises(WrongEventError):
        verify_race_identity(_race_meta(), round=1, expected={"track": "Talladega Superspeedway"})


def test_no_identity_raises():
    with pytest.raises(WrongEventError):
        verify_race_identity({}, round=1, expected={})


def test_feed_source_refuses_wrong_weekend_payload():
    """A weekend feed whose own race block disagrees with the race list entry
    it was fetched for must raise, never parse."""
    rl = load_fixture("race_list_sample.json")
    wrong = load_fixture("weekend_feed_sample.json")  # Bristol payload...
    client = FakeCacherClient(
        race_lists={SEASON: rl},
        weekends={(SEASON, 5596): wrong},  # ...served for the Daytona race_id
    )
    src = NascarFeedSource(client=client)
    with pytest.raises(WrongEventError):
        src.race_rows(SEASON, 1)


def test_wrong_season_race_list_is_refused():
    """The cacher answers pre-archive years with its EARLIEST season; the
    race_season guard must refuse it (2018 must never be ingested as 2017)."""
    rl = copy.deepcopy(load_fixture("race_list_sample.json"))
    for r in rl["series_1"]:
        r["race_season"] = 2018
    src = NascarFeedSource(client=FakeCacherClient(race_lists={2017: rl}))
    assert src.season_races(2017) is None
    assert src.results(2017, 1) is None


def test_active_calendar_cross_check():
    """For the ACTIVE season the race list entry must match the human-verified
    config calendar (race_id + date + track)."""
    rl = copy.deepcopy(load_fixture("race_list_sample.json"))
    # Corrupt round 1's race id in the list.
    pts = [r for r in rl["series_1"] if r["race_type_id"] == 1]
    daytona = next(r for r in pts if r["race_id"] == 5596)
    daytona["race_id"] = 9999
    src = NascarFeedSource(client=FakeCacherClient(race_lists={SEASON: rl}))
    with pytest.raises(WrongEventError):
        src.race_rows(SEASON, 1)


def test_refresh_refuses_calendar_count_drift(monkeypatch):
    """A cancelled/added event changes the points-race count — refresh must
    refuse until a human re-verifies round numbering."""
    from nascar_predictions import refresh

    class _Src:
        def season_races(self, year):
            return [{"race_id": i} for i in range(35)]  # 35 != 36

    with pytest.raises(WrongEventError):
        refresh.build_snapshot(SEASON, source=_Src())
