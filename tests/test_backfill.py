"""Tests for the historical-backfill pipeline.

We mock every FastF1 call: the test runner must never hit the network.
The DB-side tests use temp paths so the repo's `data/history.duckdb` (if any)
is left untouched.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest

import backfill_history as bh
from leakage import LeakageError, assert_seasons_prior_only
from models.calibration import ProbabilityCalibrator


# --------------------------------------------------------------------------- #
# Synthetic data builder — 3 rounds, 22 drivers
# --------------------------------------------------------------------------- #


DRIVERS_22 = [
    "VER", "HAD", "NOR", "PIA", "LEC", "HAM",
    "ANT", "RUS", "ALO", "STR", "GAS", "COL",
    "ALB", "SAI", "LAW", "LIN", "OCO", "BEA",
    "BOR", "HUL", "PER", "BOT",
]


def _fake_actuals(rnd: int) -> dict[str, int]:
    """Deterministic finishing positions per round.

    Round 1: identity order. Round 2: VER and NOR swap. Round 3: reverse.
    """
    if rnd == 1:
        order = DRIVERS_22
    elif rnd == 2:
        order = [DRIVERS_22[2], DRIVERS_22[1], DRIVERS_22[0]] + DRIVERS_22[3:]
    else:  # rnd == 3
        order = list(reversed(DRIVERS_22))
    return {drv: pos + 1 for pos, drv in enumerate(order)}


def _fake_pace(rnd: int) -> dict[str, float]:
    """Predicted lap times that map to a known finishing-prediction ordering.

    Round 1 prediction matches actual order (perfect). Round 2 prediction
    matches actual order EXCEPT we keep VER first (so the model "missed"
    the VER-NOR swap). Round 3 prediction is again identity (so the model
    badly missed the reversal — useful for calibration signal).
    """
    if rnd == 2:
        order = DRIVERS_22  # model thinks identity; actual swapped VER↔NOR
    else:
        # Rounds 1 and 3 the model predicts identity; round 1 it's right,
        # round 3 it's wrong (actual = reverse).
        order = DRIVERS_22
    return {drv: 80.0 + 0.05 * i for i, drv in enumerate(order)}


@pytest.fixture
def patched_fastf1():
    """Patch backfill_history's FastF1 entry points with deterministic fakes.

    Both ``fetch_session_results`` and ``fetch_race_lap_times`` are replaced;
    the underlying ``fastf1.get_session`` is never called in tests.
    """
    def _results(year: int, rnd: int) -> dict[str, int]:
        if year == 2025 and rnd in (1, 2, 3):
            return _fake_actuals(rnd)
        # Prior-season fetches return empty so prior-pace aggregation skips them.
        return {}

    def _laps(year: int, rnd: int) -> dict[str, float]:
        # For the target year 2025 prior-rounds fetch, give back a deterministic
        # pace; for prior-season calls (2024, 2023) also return a useful pace
        # so aggregation produces something.
        if year in (2023, 2024, 2025) and rnd in (1, 2, 3):
            return _fake_pace(rnd)
        return {}

    with patch.object(bh, "fetch_session_results", side_effect=_results), \
         patch.object(bh, "fetch_race_lap_times", side_effect=_laps):
        yield


# --------------------------------------------------------------------------- #
# DB round-trip
# --------------------------------------------------------------------------- #


class TestDBRoundTrip:
    def test_schema_creates_table(self, tmp_path: Path):
        db = tmp_path / "h.duckdb"
        conn = bh.connect(db)
        # Table exists and is queryable.
        rows = conn.execute(
            "SELECT COUNT(*) FROM historical_predictions"
        ).fetchone()
        assert rows is not None
        assert rows[0] == 0
        conn.close()

    def test_insert_and_count(self, tmp_path: Path, patched_fastf1):
        db = tmp_path / "h.duckdb"
        result = bh.backfill(
            seasons=[2025],
            rounds=[1, 2, 3],
            db_path=db,
            show_progress=False,
        )
        assert result["rounds_written"] == 3
        assert result["rounds_skipped"] == 0

        conn = duckdb.connect(str(db))
        total = conn.execute(
            "SELECT COUNT(*) FROM historical_predictions"
        ).fetchone()[0]
        # 3 rounds * 22 drivers = 66 rows.
        assert total == 66
        # Distinct rounds.
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT (season, round)) FROM historical_predictions"
        ).fetchone()[0]
        assert distinct == 3
        conn.close()

    def test_default_skips_existing(self, tmp_path: Path, patched_fastf1):
        db = tmp_path / "h.duckdb"
        first = bh.backfill(
            seasons=[2025], rounds=[1], db_path=db, show_progress=False
        )
        assert first["rounds_written"] == 1
        # Second call without --force: must skip.
        second = bh.backfill(
            seasons=[2025], rounds=[1], db_path=db, show_progress=False
        )
        assert second["rounds_written"] == 0
        assert second["rounds_skipped"] == 1

    def test_force_overwrites(self, tmp_path: Path, patched_fastf1):
        db = tmp_path / "h.duckdb"
        bh.backfill(
            seasons=[2025], rounds=[1], db_path=db, show_progress=False
        )
        # With --force the row count stays the same (re-inserts).
        result = bh.backfill(
            seasons=[2025],
            rounds=[1],
            db_path=db,
            force=True,
            show_progress=False,
        )
        assert result["rounds_written"] == 1
        assert result["rounds_skipped"] == 0
        conn = duckdb.connect(str(db))
        total = conn.execute(
            "SELECT COUNT(*) FROM historical_predictions"
        ).fetchone()[0]
        # Still 22 rows for the single round — not 44.
        assert total == 22
        conn.close()


# --------------------------------------------------------------------------- #
# Calibrator history conversion
# --------------------------------------------------------------------------- #


class TestHistoryRecords:
    def test_record_count_and_shape(self, tmp_path: Path, patched_fastf1):
        db = tmp_path / "h.duckdb"
        bh.backfill(
            seasons=[2025],
            rounds=[1, 2, 3],
            db_path=db,
            show_progress=False,
        )
        records = bh.load_history_records(db)
        # 3 rounds * 22 drivers * 4 markets = 264 records.
        assert len(records) == 264
        # Every record has the calibrator-required keys and value ranges.
        for r in records:
            assert r["market"] in {"win", "podium", "top6", "top10"}
            assert 0.0 <= r["predicted"] <= 1.0
            assert r["observed"] in (0, 1)

    def test_calibrator_fits_from_db_records(
        self, tmp_path: Path, patched_fastf1
    ):
        db = tmp_path / "h.duckdb"
        bh.backfill(
            seasons=[2025],
            rounds=[1, 2, 3],
            db_path=db,
            show_progress=False,
        )
        records = bh.load_history_records(db)
        cal = ProbabilityCalibrator()
        cal.fit_from_history(records)
        # All four markets must clear the calibrator's `_min_samples` gate.
        for market in ("win", "podium", "top6", "top10"):
            assert cal.is_fitted(market), (
                f"calibrator did not fit market={market} "
                f"from {len(records)} records"
            )

    def test_distinct_rounds_counter(self, tmp_path: Path, patched_fastf1):
        db = tmp_path / "h.duckdb"
        bh.backfill(
            seasons=[2025], rounds=[1, 2, 3], db_path=db, show_progress=False
        )
        assert bh.count_distinct_rounds(db) == 3

    def test_missing_db_returns_empty(self, tmp_path: Path):
        db = tmp_path / "missing.duckdb"
        assert bh.load_history_records(db) == []
        assert bh.count_distinct_rounds(db) == 0


# --------------------------------------------------------------------------- #
# Leakage discipline in the aggregator
# --------------------------------------------------------------------------- #


class TestLeakage:
    def test_assert_seasons_prior_only_used_inline(self):
        """Sanity: confirm the helper rejects a deliberately broken input."""
        broken = [
            {"season": 2025, "round": 5},  # equal to target round → leakage
            {"season": 2025, "round": 6},  # future round  → leakage
        ]
        with pytest.raises(LeakageError):
            assert_seasons_prior_only(
                broken,
                current_season=2025,
                current_round=5,
                label="test-input",
            )
        # Older season is always safe.
        ok = [{"season": 2024, "round": 22}, {"season": 2025, "round": 4}]
        assert_seasons_prior_only(
            ok, current_season=2025, current_round=5
        )

    def test_aggregator_only_uses_prior_data(self, patched_fastf1):
        """No (season, round) >= target is consulted by the aggregator.

        We spy on `fetch_race_lap_times` to record every (year, rnd) it sees,
        then assert that recorded set passes `assert_seasons_prior_only`.
        """
        seen: list[dict[str, int]] = []
        original = bh.fetch_race_lap_times

        def spy(year: int, rnd: int):
            seen.append({"season": year, "round": rnd})
            return original(year, rnd)

        with patch.object(bh, "fetch_race_lap_times", side_effect=spy):
            bh.aggregate_prior_pace(target_season=2025, target_round=5)

        # Every recorded fetch must be strictly prior to (2025, 5).
        assert_seasons_prior_only(
            seen, current_season=2025, current_round=5,
            label="aggregator-spy",
        )

    def test_build_round_rows_round1_skips_same_season_history(
        self, patched_fastf1
    ):
        """Round 1 has no prior same-season rounds — aggregator must not crash."""
        rows = bh.build_round_rows(2025, 1)
        # 22 driver rows, all carry the round = 1 attribute.
        assert len(rows) == 22
        assert {r.round for r in rows} == {1}


# --------------------------------------------------------------------------- #
# CLI parsing helpers
# --------------------------------------------------------------------------- #


class TestCLIParsers:
    def test_parse_seasons_basic(self):
        assert bh._parse_seasons("2023,2024,2025") == [2023, 2024, 2025]
        assert bh._parse_seasons("2024") == [2024]

    def test_parse_rounds_range(self):
        assert bh._parse_rounds("1-3") == [1, 2, 3]
        assert bh._parse_rounds("1,3,5") == [1, 3, 5]
        assert bh._parse_rounds(None) is None


# --------------------------------------------------------------------------- #
# End-to-end: export_probabilities reads the DB and flips `applied=true`.
# --------------------------------------------------------------------------- #


class TestExportProbabilitiesGate:
    """Confirm a freshly-built DB flips `calibration.applied=true` end-to-end.

    The exporter is run round-less (no website round JSONs in the test
    sandbox), but we hit the DB-loader code path and assert the gate count.
    """

    def test_db_history_loads_and_clears_gate(
        self, tmp_path: Path, patched_fastf1
    ):
        db = tmp_path / "h.duckdb"
        bh.backfill(
            seasons=[2025],
            rounds=[1, 2, 3],
            db_path=db,
            show_progress=False,
        )
        # 3 distinct rounds → at or above the default min_completed_rounds=3.
        from export_probabilities import _load_history_from_db

        records, n_rounds = _load_history_from_db(db)
        assert n_rounds == 3
        assert len(records) == 264

        cal = ProbabilityCalibrator()
        cal.fit_from_history(records)
        assert cal.is_fitted("win")
        assert cal.is_fitted("podium")
