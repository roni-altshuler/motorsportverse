"""Source layer: feed parsing (fixtures), snapshot serving, composite fallback."""
from __future__ import annotations

from conftest import FakeCacherClient, load_fixture

from nascar_predictions import config
from nascar_predictions.sources.composite import CompositeNascarSource
from nascar_predictions.sources.nascar_feed_source import (
    NascarFeedSource,
    parse_qualifying,
    parse_result_rows,
    parse_stage_results,
    points_races,
    race_is_complete,
)
from nascar_predictions.sources.synthetic import SyntheticNascarSource

SEASON = config.SEASON


# --------------------------------------------------------------------------- #
# Pure feed parsing (offline fixtures)
# --------------------------------------------------------------------------- #
def test_points_races_filters_and_orders_by_date():
    rl = load_fixture("race_list_sample.json")
    picked = points_races(rl)
    # The fixture interleaves Clash/Duels (race_type_id != 1) and shuffles the
    # order; the filter keeps points races only, date-ordered.
    assert [r["race_id"] for r in picked] == [5596, 5597, 5598]
    assert all(r["race_type_id"] == 1 for r in picked)


def test_parse_result_rows_shapes_and_dnf():
    feed = load_fixture("weekend_feed_sample.json")
    rows = parse_result_rows(feed["weekend_race"][0]["results"])
    assert rows[0]["position"] == 1
    assert rows[0]["code"] == "TYGIBBS"  # Ty Gibbs won Bristol (verified live)
    assert rows == sorted(rows, key=lambda r: r["position"])
    # Every row carries the attrition + scoring fields the model consumes.
    for r in rows:
        assert set(r) >= {
            "position", "code", "name", "team", "make", "grid", "status",
            "dnf", "points", "playoffPoints", "lapsLed", "pointsPosition",
        }
    dnfs = [r for r in rows if r["dnf"]]
    assert dnfs and all(r["status"] != "Running" for r in dnfs)
    runners = [r for r in rows if not r["dnf"]]
    assert all(r["status"] == "Running" for r in runners)


def test_parse_stage_results():
    feed = load_fixture("weekend_feed_sample.json")
    stages = parse_stage_results(feed["weekend_race"][0])
    assert set(stages) == {"1", "2"}
    s1 = stages["1"]
    assert s1[0]["position"] == 1 and s1[0]["points"] == 10.0
    assert s1[0]["code"] == "KYLARSON"  # Larson won stage 1 at Bristol


def test_parse_qualifying_orders_by_position():
    feed = load_fixture("weekend_feed_sample.json")
    order = parse_qualifying(feed)
    assert order is not None and order[0] == "RYBLANEY"  # Blaney on pole
    assert len(order) == len(set(order))


def test_race_is_complete_rejects_preseeded_future_entry_list():
    """A FUTURE race's feed serves a full results array with empty statuses —
    it must never count as a completed classification."""
    future = load_fixture("weekend_feed_future.json")
    rows = future["weekend_race"][0]["results"]
    assert rows  # positions are pre-seeded...
    assert not race_is_complete(rows)  # ...but the race has not run
    done = load_fixture("weekend_feed_sample.json")
    assert race_is_complete(done["weekend_race"][0]["results"])


def test_feed_source_entry_list_from_future_feed():
    rl = load_fixture("race_list_sample.json")
    future = load_fixture("weekend_feed_future.json")
    # Make the future feed answer for round 2 (Atlanta, race_id 5597).
    future["weekend_race"][0]["race_id"] = 5597
    future["weekend_race"][0]["race_date"] = "2026-02-22T15:00:00"
    future["weekend_race"][0]["track_name"] = "Atlanta Motor Speedway"
    client = FakeCacherClient(race_lists={SEASON: rl}, weekends={(SEASON, 5597): future})
    src = NascarFeedSource(client=client)
    assert src.results(SEASON, 2) == []          # known round, not run yet
    assert src.race_rows(SEASON, 2) is None
    entries = src.entry_list(SEASON, 2)
    assert entries and all(isinstance(c, str) for c in entries)


def test_feed_source_none_when_network_down():
    src = NascarFeedSource(client=FakeCacherClient())  # serves nothing
    assert src.season_races(SEASON) is None
    assert src.results(SEASON, 1) is None


# --------------------------------------------------------------------------- #
# Snapshot + composite
# --------------------------------------------------------------------------- #
def test_snapshot_serves_committed_rounds(snapshot_source):
    res = snapshot_source.results(SEASON, 1)
    assert res and res[0].position == 1
    rows = snapshot_source.race_rows(SEASON, 1)
    assert rows and len(rows) >= 36
    stages = snapshot_source.stage_results(SEASON, 1)
    assert stages and "1" in stages
    assert snapshot_source.qualifying(SEASON, 1)
    assert len(snapshot_source.completed_rounds(SEASON)) >= 19


def test_snapshot_serves_archived_seasons(snapshot_source):
    res = snapshot_source.results(2022, 1)
    assert res and res[0].position == 1
    cal = snapshot_source.calendar(2022)
    assert len(cal) == 36
    assert cal[0]["trackType"] == "superspeedway"  # Daytona 500


def test_snapshot_none_for_unknown_season(snapshot_source):
    assert snapshot_source.results(2016, 1) is None


def test_composite_provenance_real_then_synthetic():
    comp = CompositeNascarSource.default()
    assert comp.results(SEASON, 1)
    assert comp.provenance(SEASON, 1) == "snapshot"
    assert CompositeNascarSource.is_real("snapshot")
    assert CompositeNascarSource.is_real("nascar-feed")
    assert not CompositeNascarSource.is_real("synthetic")


def test_synthetic_never_answers_for_past_seasons():
    syn = SyntheticNascarSource()
    assert syn.results(2024, 1) == []
    res = syn.results(SEASON, 1)
    assert res  # active season, completed round
    # NASCAR classifies every car: synthetic retirees carry positions + status.
    dnfs = [r for r in res if r.status != "Running"]
    assert all(r.position is not None for r in res)
    assert dnfs, "synthetic generator must produce attrition signal"
