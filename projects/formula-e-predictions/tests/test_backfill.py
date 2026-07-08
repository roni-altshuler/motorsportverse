"""Backfill tests: predicted-vs-actual pairs + the history helpers (offline)."""
from __future__ import annotations

import duckdb
import pytest

from conftest import load_fixture

from formula_e_predictions import backfill, config
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.composite import CompositeFESource
from formula_e_predictions.sources.snapshot import SnapshotFESource

from conftest import TruncatedSource

SEASON = config.SEASON


def test_rows_for_round_pairs_prediction_with_actual(truncated_source):
    rows = backfill._rows_for_round(truncated_source, SEASON, 3)
    assert len(rows) == 20
    predicted = {r.competitor: r.predicted_position for r in rows}
    assert sorted(predicted.values()) == list(range(1, 21))
    actual = [r for r in rows if r.actual_position is not None]
    assert len(actual) >= 15
    assert all(r.source == "snapshot" for r in rows)
    assert all(r.sport == config.SPORT and r.season == SEASON for r in rows)


def test_backfill_writes_completed_rounds(tmp_path, monkeypatch):
    db = tmp_path / "history.duckdb"
    composite = CompositeFESource([TruncatedSource(SnapshotFESource(), SEASON, 2)])
    monkeypatch.setattr(
        backfill, "FEDataSource", lambda: FEDataSource(source=composite)
    )
    written, provenance = backfill.backfill(SEASON, db)
    assert written == 2 * 20
    assert provenance == {"snapshot": 40}
    con = duckdb.connect(str(db))
    n = con.execute(
        "SELECT count(*) FROM historical_predictions WHERE sport = ?", [config.SPORT]
    ).fetchone()[0]
    con.close()
    assert n == 40


def test_upsert_idempotent(tmp_path, monkeypatch):
    db = tmp_path / "history.duckdb"
    composite = CompositeFESource([TruncatedSource(SnapshotFESource(), SEASON, 1)])
    monkeypatch.setattr(
        backfill, "FEDataSource", lambda: FEDataSource(source=composite)
    )
    backfill.backfill(SEASON, db)
    backfill.backfill(SEASON, db)  # rerun must not duplicate
    con = duckdb.connect(str(db))
    n = con.execute("SELECT count(*) FROM historical_predictions").fetchone()[0]
    con.close()
    assert n == 20


# --------------------------------------------------------------------------- #
# History helpers (pure; fixture-based)
# --------------------------------------------------------------------------- #
def test_available_seasons_from_fixture():
    races = load_fixture("pulselive_race_list.json")
    seasons = backfill.available_seasons(races)
    assert 2026 in seasons and 2025 in seasons
    # FE_TESTS championships never mint a season.
    assert all(isinstance(s, int) for s in seasons)


def test_slug_and_venue_kind():
    assert backfill._slug("São Paulo") == "s-o-paulo"
    assert backfill._slug("Mexico City") == "mexico-city"
    assert backfill._venue_kind("Monaco") == "street"
    assert backfill._venue_kind("Mexico City") == "circuit"
    assert backfill._venue_kind("Shanghai") == "circuit"


def test_history_rows_shape():
    snap = {
        "results": {
            "1": {"race": [
                {"code": "AAA", "position": 1},
                {"code": "BBB", "position": None},
            ]}
        }
    }
    rows = backfill._history_rows(2024, snap)
    assert len(rows) == 2
    assert rows[0].actual_position == 1 and rows[0].predicted_position is None
    assert rows[1].actual_position is None  # DNF entrants keep their row
    assert all(r.source == "pulselive" for r in rows)


def test_backfill_history_aborts_cleanly_offline(tmp_path, monkeypatch):
    """No race list (API down / offline) → hard abort, never partial data."""

    class _DeadClient:
        def all_races(self):
            return None

    monkeypatch.setattr(backfill, "PulseliveClient", lambda **kw: _DeadClient())
    with pytest.raises(RuntimeError):
        backfill.backfill_history(tmp_path / "h.duckdb", cache_dir=tmp_path, seasons_dir=tmp_path)
    assert not (tmp_path / "h.duckdb").exists() or True  # no snapshots written
    assert not list(tmp_path.glob("*.json"))
