"""Smoke + unit tests for motorsport-data (no network, no duckdb required)."""

from pathlib import Path

import pytest

from motorsport_data import rollover, schema


def test_schema_round_trips():
    s = schema.Season(
        sport="Formula 1",
        year=2026,
        competitors=[schema.Competitor(code="VER", name="Max Verstappen", team="Red Bull")],
        calendar=[schema.Venue(key="monaco", name="Monaco Grand Prix", country="Monaco")],
        completed_rounds=[1, 2],
    )
    blob = s.model_dump_json()
    again = schema.Season.model_validate_json(blob)
    assert again.competitors[0].code == "VER"
    assert again.calendar[0].kind == schema.VenueKind.circuit


def test_prediction_optional_fields():
    p = schema.Prediction(competitor="HAM", predicted_position=3, p_win=0.12)
    assert p.low is None and p.p_podium is None


def test_archive_season(tmp_path: Path):
    root = tmp_path / "data"
    (root / "rounds").mkdir(parents=True)
    (root / "season.json").write_text('{"year": 2025}')
    (root / "rounds" / "round_01.json").write_text("{}")
    cfg = rollover.RolloverConfig(data_root=root)
    dest = rollover.archive_season(cfg, 2025)
    assert (dest / "season.json").exists()
    assert (dest / "rounds" / "round_01.json").exists()


def test_auto_rollover_noop_when_incomplete(tmp_path: Path):
    cfg = rollover.RolloverConfig(data_root=tmp_path)
    assert rollover.auto_rollover(cfg, 2025, active_complete=False, available_years=[2025, 2026]) is None


def test_auto_rollover_advances(tmp_path: Path):
    (tmp_path / "season.json").write_text("{}")
    cfg = rollover.RolloverConfig(data_root=tmp_path)
    new = rollover.auto_rollover(cfg, 2025, active_complete=True, available_years=[2025, 2026])
    assert new == {"year": 2026, "completed_rounds": [], "active": True}


def test_store_requires_duckdb_gracefully():
    # store module imports fine even without constructing a connection
    from motorsport_data import store

    assert store.SCHEMA.strip().startswith("CREATE TABLE")
    row = store.HistoryRow(sport="Formula 1", season=2026, round=1, competitor="VER")
    assert row.predicted_position is None


def test_jolpica_import_does_not_require_requests():
    # module import must not eagerly import requests
    from motorsport_data.sources import jolpica

    assert jolpica.BASE_URL.startswith("https://")


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("duckdb") is None,
    reason="duckdb not installed",
)
def test_history_store_roundtrip(tmp_path: Path):
    from motorsport_data import store

    st = store.HistoryStore(tmp_path / "h.duckdb")
    st.upsert(
        [
            store.HistoryRow("Formula 1", 2026, 1, "VER", 1, 1, 78.2, "test"),
            store.HistoryRow("Formula 1", 2026, 1, "HAM", 2, 3, 78.5, "test"),
        ]
    )
    assert st.completed_rounds("Formula 1", 2026) == [1]
    assert sorted(st.pairs("Formula 1")) == [(1, 1), (2, 3)]
    st.close()
