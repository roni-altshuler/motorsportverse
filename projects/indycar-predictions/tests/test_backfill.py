"""Backfill: the committed archive → DuckDB (offline!) + predicted-vs-actual pairs."""
from __future__ import annotations

import pytest

from indycar_predictions import backfill, config

SEASON = config.SEASON


def test_history_rows_from_committed_files(snapshot_source):
    rows = backfill._history_rows(snapshot_source, 2019)
    assert rows and all(r.sport == config.SPORT and r.season == 2019 for r in rows)
    assert all(r.actual_position is not None for r in rows)
    assert all(r.source == "snapshot" for r in rows)
    # 17 rounds in 2019 (curated) — a full field per round.
    assert len({r.round for r in rows}) == 17


def test_backfill_history_is_offline(tmp_path):
    """--history loads straight from the committed files — no network at all."""
    pytest.importorskip("duckdb")
    db = tmp_path / "history.duckdb"
    report = backfill.backfill_history(db, first_season=2024, upto_season=2025)
    assert set(report["seasons"]) == {2024, 2025}
    assert report["seasons"][2024]["rounds"] == 17
    assert report["rows"] > 800  # two seasons of ~27-car fields

    from motorsport_data.store import HistoryStore

    store = HistoryStore(db)
    try:
        assert store.completed_rounds(config.SPORT, 2024) == list(range(1, 18))
    finally:
        store.close()


def test_offline_pairs_roundtrip(tmp_path, real_source):
    """One round's predicted-vs-actual rows written to a fresh store."""
    pytest.importorskip("duckdb")
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
