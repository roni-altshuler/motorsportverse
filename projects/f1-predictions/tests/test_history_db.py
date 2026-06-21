"""Tests for the Ergast/Jolpica historical backfill + schema migration.

The Jolpica HTTP layer is mocked end-to-end; the test runner must never
hit the network.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import backfill_history as bh
import ergast_backfill as eb


# --------------------------------------------------------------------------- #
# Synthetic Jolpica race payloads
# --------------------------------------------------------------------------- #


def _race_payload(
    season: int,
    rnd: int,
    *,
    drivers: list[tuple[str, int, int]],  # (code, grid, position)
) -> dict:
    """Build a minimal Jolpica-shaped race dict from triples.

    Keys mirror the live API's RaceTable.Races[i] structure — only the
    fields ``race_to_rows`` reads are included; the parser must tolerate
    everything else being absent.
    """
    return {
        "season": str(season),
        "round": str(rnd),
        "Results": [
            {
                "position": str(position),
                "grid": str(grid),
                "Driver": {"code": code, "driverId": code.lower()},
            }
            for code, grid, position in drivers
        ],
    }


def _season_payload(season: int, races_spec: dict[int, list[tuple[str, int, int]]]) -> list[dict]:
    """Wrap multiple race payloads in a deterministic order."""
    return [_race_payload(season, rnd, drivers=drivers) for rnd, drivers in races_spec.items()]


# --------------------------------------------------------------------------- #
# race_to_rows — parser correctness
# --------------------------------------------------------------------------- #


def test_race_to_rows_extracts_finishing_position_and_grid() -> None:
    race = _race_payload(
        season=2024,
        rnd=5,
        drivers=[("VER", 1, 1), ("NOR", 3, 2), ("LEC", 2, 3)],
    )
    rows = eb.race_to_rows(race)

    assert {r.driver for r in rows} == {"VER", "NOR", "LEC"}
    by_drv = {r.driver: r for r in rows}
    assert by_drv["VER"].actual_position == 1
    assert by_drv["VER"].predicted_position == 1  # grid 1
    assert by_drv["NOR"].actual_position == 2
    assert by_drv["NOR"].predicted_position == 3  # grid 3
    # No lap times from Ergast tier
    for r in rows:
        assert r.predicted_lap_time is None
        assert r.season == 2024
        assert r.round == 5


def test_race_to_rows_treats_grid_zero_as_null_prediction() -> None:
    """Ergast convention: grid='0' = pit-lane start, not a real grid slot."""
    race = _race_payload(season=2024, rnd=1, drivers=[("HAM", 0, 7)])
    rows = eb.race_to_rows(race)
    assert len(rows) == 1
    assert rows[0].predicted_position is None
    assert rows[0].actual_position == 7


def test_race_to_rows_falls_back_to_driver_id_when_code_missing() -> None:
    """Historical (pre-1980) entries often omit Driver.code."""
    race = {
        "season": "1955",
        "round": "1",
        "Results": [
            {
                "position": "1",
                "grid": "1",
                "Driver": {"driverId": "fangio"},  # no 'code'
            }
        ],
    }
    rows = eb.race_to_rows(race)
    assert len(rows) == 1
    assert rows[0].driver == "FANGIO"


def test_race_to_rows_skips_entries_without_any_driver_identifier() -> None:
    race = {
        "season": "1950",
        "round": "1",
        "Results": [
            {"position": "1", "grid": "1", "Driver": {}},
            {"position": "2", "grid": "2", "Driver": {"code": "OK1"}},
        ],
    }
    rows = eb.race_to_rows(race)
    assert {r.driver for r in rows} == {"OK1"}


def test_race_to_rows_handles_malformed_season_or_round() -> None:
    """Garbage in → empty list out; never crash the orchestrator."""
    assert eb.race_to_rows({"season": "not-a-year", "round": "1", "Results": []}) == []
    assert eb.race_to_rows({"season": "2024", "round": None, "Results": []}) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3", 3),
        ("0", 0),
        (None, None),
        ("", None),
        ("not-a-number", None),
        (5, 5),
    ],
)
def test_safe_int_edge_cases(raw: object, expected: int | None) -> None:
    assert eb._safe_int(raw) == expected


# --------------------------------------------------------------------------- #
# Schema migration
# --------------------------------------------------------------------------- #


def test_ensure_source_column_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "history.duckdb"
    conn = bh.connect(db)
    eb.ensure_source_column(conn)
    eb.ensure_source_column(conn)  # second call must not raise
    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'historical_predictions'"
        ).fetchall()
    }
    assert "source" in columns
    conn.close()


def test_ensure_source_column_back_fills_existing_rows_to_fastf1(tmp_path: Path) -> None:
    """Adding `source` to a pre-existing table must default existing rows."""
    db = tmp_path / "history.duckdb"
    conn = bh.connect(db)
    bh.insert_rows(
        conn,
        [bh.HistoryRow(season=2024, round=1, driver="VER",
                       predicted_position=1, actual_position=1, predicted_lap_time=82.4)],
    )
    eb.ensure_source_column(conn)
    sources = [
        row[0]
        for row in conn.execute(
            "SELECT source FROM historical_predictions WHERE season=2024 AND round=1"
        ).fetchall()
    ]
    assert sources == ["fastf1"]
    conn.close()


# --------------------------------------------------------------------------- #
# backfill_seasons — orchestration
# --------------------------------------------------------------------------- #


def test_backfill_seasons_writes_rows_with_ergast_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "history.duckdb"

    def fake_fetch_season_results(year: int, **_: object) -> list[dict]:
        return _season_payload(year, {
            1: [("ARG", 1, 1), ("BRA", 2, 2)],
            2: [("ARG", 2, 1), ("BRA", 1, 3)],
        })

    monkeypatch.setattr(eb, "fetch_season_results", fake_fetch_season_results)

    result = eb.backfill_seasons(
        seasons=[2010],
        db_path=db,
        force=False,
        show_progress=False,
        per_request_sleep_s=0.0,
    )

    assert result["rounds_written"] == 2
    assert result["rounds_failed"] == 0

    conn = duckdb.connect(str(db), read_only=True)
    sources_seen = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT source FROM historical_predictions WHERE season=2010"
        ).fetchall()
    }
    assert sources_seen == {"ergast"}
    distinct_rounds = conn.execute(
        "SELECT COUNT(DISTINCT round) FROM historical_predictions WHERE season=2010"
    ).fetchone()[0]
    assert distinct_rounds == 2
    conn.close()


def test_backfill_seasons_skips_existing_rounds_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Idempotency: a second pass should not duplicate rows for the same round."""
    db = tmp_path / "history.duckdb"

    payload = lambda year: _season_payload(year, {  # noqa: E731
        1: [("ARG", 1, 1), ("BRA", 2, 2)],
    })
    monkeypatch.setattr(eb, "fetch_season_results", lambda year, **_: payload(year))

    first = eb.backfill_seasons(
        seasons=[2010], db_path=db, force=False, show_progress=False, per_request_sleep_s=0.0
    )
    second = eb.backfill_seasons(
        seasons=[2010], db_path=db, force=False, show_progress=False, per_request_sleep_s=0.0
    )

    assert first["rounds_written"] == 1
    assert second["rounds_written"] == 0
    assert second["rounds_skipped"] == 1


def test_backfill_seasons_force_replaces_existing_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "history.duckdb"

    state = {"actual_pos": 2}

    def fake_fetch(year: int, **_: object) -> list[dict]:
        return _season_payload(year, {
            1: [("ARG", 1, state["actual_pos"])],
        })

    monkeypatch.setattr(eb, "fetch_season_results", fake_fetch)

    eb.backfill_seasons([2010], db_path=db, force=False, show_progress=False, per_request_sleep_s=0.0)
    state["actual_pos"] = 5  # simulate Jolpica revising the result
    eb.backfill_seasons([2010], db_path=db, force=True, show_progress=False, per_request_sleep_s=0.0)

    conn = duckdb.connect(str(db), read_only=True)
    actual = conn.execute(
        "SELECT actual_position FROM historical_predictions "
        "WHERE season=2010 AND round=1 AND driver='ARG'"
    ).fetchone()[0]
    conn.close()
    assert actual == 5


def test_backfill_seasons_coexists_with_fastf1_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB with both Tier 1 (fastf1) and Tier 2 (ergast) rows must be filterable."""
    db = tmp_path / "history.duckdb"

    # Tier 1: write a row directly via backfill_history's path
    conn = bh.connect(db)
    bh.insert_rows(
        conn,
        [bh.HistoryRow(season=2024, round=1, driver="VER",
                       predicted_position=1, actual_position=1, predicted_lap_time=82.4)],
    )
    conn.close()

    # Tier 2: ergast backfill of a non-overlapping season
    monkeypatch.setattr(
        eb,
        "fetch_season_results",
        lambda year, **_: _season_payload(year, {1: [("FAN", 1, 1)]}),
    )
    eb.backfill_seasons([1955], db_path=db, force=False, show_progress=False, per_request_sleep_s=0.0)

    conn = duckdb.connect(str(db), read_only=True)
    by_source = dict(
        conn.execute(
            "SELECT source, COUNT(*) FROM historical_predictions GROUP BY source"
        ).fetchall()
    )
    conn.close()
    assert by_source["fastf1"] == 1
    assert by_source["ergast"] == 1


def test_backfill_rejects_pre_1950_seasons(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        eb.backfill_seasons(
            [1949], db_path=tmp_path / "history.duckdb", show_progress=False
        )


def test_backfill_handles_network_failures_per_season(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If Jolpica returns no races, the season is marked failed but other
    seasons still process."""
    db = tmp_path / "history.duckdb"

    def fake_fetch(year: int, **_: object) -> list[dict]:
        if year == 1980:
            return []  # simulate network outage / 5xx
        return _season_payload(year, {1: [("ARG", 1, 1)]})

    monkeypatch.setattr(eb, "fetch_season_results", fake_fetch)

    result = eb.backfill_seasons(
        seasons=[1980, 1981],
        db_path=db,
        force=False,
        show_progress=False,
        per_request_sleep_s=0.0,
    )
    assert result["rounds_written"] == 1
    assert result["rounds_failed"] == 1


# --------------------------------------------------------------------------- #
# Calibrator compatibility — existing reader must still work post-migration
# --------------------------------------------------------------------------- #


def test_load_history_records_still_works_with_source_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """backfill_history.load_history_records reads from the same table; it must
    keep returning records after the schema migration."""
    db = tmp_path / "history.duckdb"
    monkeypatch.setattr(
        eb,
        "fetch_season_results",
        lambda year, **_: _season_payload(
            year, {1: [("ARG", 1, 1), ("BRA", 2, 2), ("URY", 3, 5)]}
        ),
    )
    eb.backfill_seasons([2010], db_path=db, force=False, show_progress=False, per_request_sleep_s=0.0)

    records = bh.load_history_records(db)
    # 3 drivers × 4 markets = 12 records, all from 2010 R1
    assert len(records) == 12
    seasons = {r["season"] for r in records}
    rounds = {r["round"] for r in records}
    assert seasons == {2010}
    assert rounds == {1}
