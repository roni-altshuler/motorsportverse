"""Tests for the race-simulator integration helper.

Covers the runner that bridges ``models/race_simulator.py`` (which knows
only about grids + race-pace artefacts) and the live export pipeline
(which has DataFrames + circuit characteristics + weather forecasts).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingRegressor

from models.race_simulator_runner import (
    RACE_PACE_METADATA_KIND,
    RACE_PACE_REGISTRY_ROUND,
    _build_grid_and_initials,
    find_latest_race_pace_entry,
    run_simulator_for_round,
)
from models.registry import ModelRegistry


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _fit_tiny_gbr() -> GradientBoostingRegressor:
    """Tiny GBR that returns a plausible lap-time when called."""
    rng = np.random.default_rng(seed=0)
    n_features = 16  # matches FEATURE_COLUMNS length
    X = rng.normal(size=(20, n_features))
    y = 80.0 + X[:, 0] * 0.1 + rng.normal(scale=0.05, size=20)
    gbr = GradientBoostingRegressor(n_estimators=10, max_depth=2, random_state=0)
    gbr.fit(X, y)
    return gbr


def _seed_race_pace_registry(tmp_path: Path, encoders: dict) -> ModelRegistry:
    """Plant a fake race-pace entry into a scratch registry."""
    reg = ModelRegistry(root=tmp_path / "registry")
    gbr = _fit_tiny_gbr()
    xgb = _fit_tiny_gbr()  # not a real XGB but the runner only calls .predict
    reg.save(
        season=2024,
        round_num=RACE_PACE_REGISTRY_ROUND,
        models={"race_pace_gbr": gbr, "race_pace_xgb": xgb},
        metadata={
            "kind": RACE_PACE_METADATA_KIND,
            "feature_columns": [
                "driver_id", "team_id", "circuit_id",
                "lap_number", "lap_progress", "track_position",
                "tyre_compound_code", "tyre_age_laps",
                "gap_to_car_ahead_s", "gap_to_car_behind_s",
                "sc_active", "vsc_active", "yellow_active",
                "air_temp_c", "track_temp_c", "rain_intensity",
            ],
            "ensemble_weights": {"gbr": 0.5, "xgb": 0.5},
            "encoders": encoders,
            "metrics": {"ensemble_mae_s": 0.42, "n_train": 100, "n_test": 25},
        },
    )
    return reg


def _make_merged(drivers: list[str]) -> pd.DataFrame:
    """A DataFrame shaped like what ``apply_race_postprocessing`` produces."""
    n = len(drivers)
    return pd.DataFrame(
        {
            "Driver": drivers,
            "Team": [f"T{i % 3}" for i in range(n)],
            "GridPosition": list(range(1, n + 1)),
            "PredictedLapTime": [80.0 + 0.15 * i for i in range(n)],
        }
    )


def _make_circuit_chars() -> dict:
    return {
        "Test": {
            "safety_car_likelihood": 0.0,  # no SC in tests for determinism
            "tyre_deg": 0.05,
            "pit_loss_s": 22.0,
            "expected_stops": 1,
            "base_quali_s": 80.0,
        }
    }


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


class TestFindLatestRacePaceEntry:
    def test_returns_none_when_registry_empty(self, tmp_path: Path):
        reg = ModelRegistry(root=tmp_path / "registry")
        assert find_latest_race_pace_entry(reg) is None

    def test_ignores_non_race_pace_entries(self, tmp_path: Path):
        reg = ModelRegistry(root=tmp_path / "registry")
        reg.save(2024, 5, {"gbr": _fit_tiny_gbr()}, metadata={"kind": "qualifying-time"})
        assert find_latest_race_pace_entry(reg) is None

    def test_returns_most_recent_race_pace_entry(self, tmp_path: Path):
        reg = ModelRegistry(root=tmp_path / "registry")
        reg.save(
            2023, RACE_PACE_REGISTRY_ROUND, {"race_pace_gbr": _fit_tiny_gbr()},
            metadata={"kind": RACE_PACE_METADATA_KIND, "tag": "older"},
        )
        reg.save(
            2024, RACE_PACE_REGISTRY_ROUND, {"race_pace_gbr": _fit_tiny_gbr()},
            metadata={"kind": RACE_PACE_METADATA_KIND, "tag": "newer"},
        )
        entry = find_latest_race_pace_entry(reg)
        assert entry is not None
        season, _, metadata = entry
        assert season == 2024
        assert metadata["tag"] == "newer"


# --------------------------------------------------------------------------- #
# Grid / initials construction
# --------------------------------------------------------------------------- #


class TestBuildGridAndInitials:
    def test_empty_merged_returns_empty(self):
        grid, initials = _build_grid_and_initials(pd.DataFrame())
        assert grid == []
        assert initials == {}

    def test_grid_sorted_by_grid_position(self):
        merged = pd.DataFrame(
            {
                "Driver": ["NOR", "VER", "LEC"],
                "Team": ["MCL", "RBR", "FER"],
                "GridPosition": [3, 1, 2],
                "PredictedLapTime": [80.5, 80.2, 80.3],
            }
        )
        grid, _ = _build_grid_and_initials(merged)
        assert [g.driver for g in grid] == ["VER", "LEC", "NOR"]
        assert [g.grid_position for g in grid] == [1, 2, 3]

    def test_pace_offset_is_relative_to_field_mean(self):
        merged = pd.DataFrame(
            {
                "Driver": ["FAST", "SLOW"],
                "Team": ["A", "B"],
                "GridPosition": [1, 2],
                "PredictedLapTime": [80.0, 82.0],
            }
        )
        _, initials = _build_grid_and_initials(merged)
        # Mean = 81.0 → FAST has -1.0, SLOW has +1.0
        assert initials["FAST"].base_pace_offset_s == pytest.approx(-1.0)
        assert initials["SLOW"].base_pace_offset_s == pytest.approx(1.0)

    def test_falls_back_to_qualifying_rank_when_grid_position_absent(self):
        merged = pd.DataFrame(
            {
                "Driver": ["A", "B", "C"],
                "Team": ["X", "Y", "Z"],
                "QualifyingRank": [2, 1, 3],
                "PredictedLapTime": [80.0, 79.5, 80.5],
            }
        )
        grid, _ = _build_grid_and_initials(merged)
        # Sorted by QualifyingRank → B(1), A(2), C(3)
        assert [g.driver for g in grid] == ["B", "A", "C"]


# --------------------------------------------------------------------------- #
# Public entry — full integration
# --------------------------------------------------------------------------- #


class TestRunSimulatorForRound:
    def test_returns_none_when_no_race_pace_model_registered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Empty registry
        monkeypatch.setattr(
            "models.race_simulator_runner.ModelRegistry",
            lambda: ModelRegistry(root=tmp_path / "registry"),
        )
        merged = _make_merged(["VER", "NOR", "LEC"])
        result = run_simulator_for_round(
            season=2024, round_num=8, gp_key="Test",
            merged=merged, weather=None, total_laps=10,
            circuit_characteristics=_make_circuit_chars(),
            n_samples=10,
        )
        assert result is None

    def test_returns_none_when_registry_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("F1_REGISTRY_ENABLED", "0")
        merged = _make_merged(["VER", "NOR"])
        result = run_simulator_for_round(
            season=2024, round_num=8, gp_key="Test",
            merged=merged, weather=None, total_laps=10,
            circuit_characteristics=_make_circuit_chars(),
            n_samples=10,
        )
        assert result is None

    def test_returns_market_probabilities_when_model_registered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        drivers = ["D00", "D01", "D02"]
        encoders = {
            "driver": {d: i for i, d in enumerate(drivers)},
            "team": {f"T{i % 3}": i for i in range(3)},
            "circuit": {"Test": 0},
        }
        _seed_race_pace_registry(tmp_path, encoders)
        monkeypatch.setattr(
            "models.race_simulator_runner.ModelRegistry",
            lambda: ModelRegistry(root=tmp_path / "registry"),
        )

        merged = _make_merged(drivers)
        result = run_simulator_for_round(
            season=2024, round_num=8, gp_key="Test",
            merged=merged, weather=None, total_laps=10,
            circuit_characteristics=_make_circuit_chars(),
            n_samples=30,
        )
        assert result is not None
        assert result["applied"] is True
        assert set(result["p_win"].keys()) == set(drivers)
        # Win probabilities sum to 1 across drivers (one winner per sample)
        assert sum(result["p_win"].values()) == pytest.approx(1.0, abs=1e-6)
        # Podium probabilities sum to 3
        assert sum(result["p_podium"].values()) == pytest.approx(3.0, abs=1e-6)
        # Metadata carries training provenance
        assert result["trained_season"] == 2024
        assert result["trained_round"] == RACE_PACE_REGISTRY_ROUND
        assert "ensemble_mae_s" in result["training_metrics"]

    def test_swallows_simulator_exceptions_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        drivers = ["D00", "D01"]
        encoders = {
            "driver": {d: i for i, d in enumerate(drivers)},
            "team": {"T0": 0, "T1": 1},
            "circuit": {"Test": 0},
        }
        _seed_race_pace_registry(tmp_path, encoders)
        monkeypatch.setattr(
            "models.race_simulator_runner.ModelRegistry",
            lambda: ModelRegistry(root=tmp_path / "registry"),
        )

        def _boom(*_: Any, **__: Any):
            raise RuntimeError("simulated lap-time prediction crash")

        # Force the simulator to crash mid-loop by patching predict_lap_times
        # inside the simulator's namespace.
        with patch("models.race_simulator.predict_lap_times", side_effect=_boom):
            result = run_simulator_for_round(
                season=2024, round_num=8, gp_key="Test",
                merged=_make_merged(drivers), weather=None, total_laps=5,
                circuit_characteristics=_make_circuit_chars(),
                n_samples=5,
            )
        # Non-fatal — the runner returns None so the export falls through
        # to the legacy projection.
        assert result is None
