"""Backfill: snapshot shaping, history rows, the offline predicted-vs-actual pass."""
from __future__ import annotations

import pytest
from conftest import FakeCacherClient, load_fixture

from nascar_predictions import backfill, config
from nascar_predictions.sources.nascar_feed_source import NascarFeedSource

SEASON = config.SEASON


def _fixture_feed_source() -> NascarFeedSource:
    rl = load_fixture("race_list_sample.json")
    feed = load_fixture("weekend_feed_sample.json")
    # Point the (Bristol) feed at the fixture list's round 1 (Daytona 5596).
    feed["weekend_race"][0]["race_id"] = 5596
    feed["weekend_race"][0]["race_date"] = "2026-02-15T14:30:00"
    feed["weekend_race"][0]["track_name"] = "Daytona International Speedway"
    client = FakeCacherClient(race_lists={2024: _reseason(rl, 2024)}, weekends={(2024, 5596): feed})
    return NascarFeedSource(client=client)


def _reseason(rl: dict, year: int) -> dict:
    import copy

    out = copy.deepcopy(rl)
    for r in out["series_1"]:
        r["race_season"] = year
    return out


def test_season_snapshot_shape_from_fixture_feed():
    src = _fixture_feed_source()
    snap = backfill._season_snapshot(src, 2024)
    assert snap["season"] == 2024
    assert snap["totalRounds"] == 3          # points races only
    assert snap["completedRounds"] == 1      # only round 1 has a completed feed
    cal = snap["calendar"]
    assert cal[0]["completed"] is True
    assert cal[0]["trackType"] == "superspeedway"
    assert cal[0]["stageLaps"] == [65, 65, 70]
    block = snap["results"]["1"]
    assert block["stages"] and block["race"][0]["position"] == 1


def test_history_rows_from_snapshot():
    src = _fixture_feed_source()
    snap = backfill._season_snapshot(src, 2024)
    rows = backfill._history_rows(2024, snap)
    assert rows and all(r.sport == config.SPORT and r.season == 2024 for r in rows)
    assert all(r.actual_position is not None for r in rows)
    assert all(r.source == "nascar-feed" for r in rows)


def test_offline_pairs_roundtrip(tmp_path, real_source):
    """One round's predicted-vs-actual rows written to a fresh store."""
    duckdb = pytest.importorskip("duckdb")  # noqa: F841
    from motorsport_data.store import HistoryStore

    rows = backfill._rows_for_round(real_source, SEASON, 2)
    assert rows and all(r.predicted_position for r in rows)
    assert any(r.actual_position for r in rows)
    assert all(r.source == "snapshot" for r in rows)
    db = tmp_path / "history.duckdb"
    store = HistoryStore(db)
    try:
        assert store.upsert(rows) == len(rows)
        assert store.completed_rounds(config.SPORT, SEASON) == [2]
    finally:
        store.close()
