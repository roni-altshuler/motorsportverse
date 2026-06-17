"""Phase 2 backfill: predicted-vs-actual pairs land in the HistoryStore."""

import pytest

from f2_predictions import backfill, config

duckdb = pytest.importorskip("duckdb")  # store backend is an optional extra


def test_backfill_writes_both_races(tmp_path):
    db = tmp_path / "history.duckdb"
    written, provenance = backfill.backfill(config.SEASON, db)

    # 2 races × 22 drivers × completed rounds.
    assert written == 2 * 22 * config.COMPLETED_ROUNDS
    assert provenance.get("synthetic", 0) == written  # default source is synthetic

    from motorsport_data.store import HistoryStore

    store = HistoryStore(db)
    try:
        completed = store.completed_rounds(config.SPORT, config.SEASON)
        # Feature rounds 1..N plus sprint rounds at the +offset sentinel.
        assert config.COMPLETED_ROUNDS in completed
        assert config.COMPLETED_ROUNDS + backfill.SPRINT_ROUND_OFFSET in completed
        pairs = store.pairs(config.SPORT)
        assert len(pairs) > 0
        assert all(1 <= p <= 22 and 1 <= a <= 22 for p, a in pairs)
    finally:
        store.close()


def test_backfill_is_idempotent(tmp_path):
    db = tmp_path / "history.duckdb"
    first, _ = backfill.backfill(config.SEASON, db)
    second, _ = backfill.backfill(config.SEASON, db)
    assert first == second  # INSERT OR REPLACE on the primary key — no duplication

    from motorsport_data.store import HistoryStore

    store = HistoryStore(db)
    try:
        rows = store._con.execute(
            "SELECT COUNT(*) FROM historical_predictions WHERE sport = ?", [config.SPORT]
        ).fetchone()[0]
        assert rows == first
    finally:
        store.close()
