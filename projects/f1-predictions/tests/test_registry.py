"""Tests for the model registry — persistence layer for trained ensembles."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression

from models.registry import (
    REGISTRY_ENV_VAR,
    ModelRegistry,
    registry_enabled,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def registry(tmp_path: Path) -> ModelRegistry:
    """A scratch registry rooted at a pytest tmp_path."""
    return ModelRegistry(root=tmp_path / "registry")


@pytest.fixture
def trained_gbr() -> GradientBoostingRegressor:
    """A tiny GBR fitted on a deterministic toy dataset."""
    rng = np.random.default_rng(seed=0)
    X = rng.normal(size=(50, 3))
    y = X @ np.array([1.0, -0.5, 0.25]) + rng.normal(scale=0.1, size=50)
    model = GradientBoostingRegressor(n_estimators=20, max_depth=2, random_state=0)
    model.fit(X, y)
    return model


@pytest.fixture
def fitted_isotonic() -> IsotonicRegression:
    """A trivial isotonic fit."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.array([0.1, 0.3, 0.6, 0.9]), np.array([0.0, 0.0, 1.0, 1.0]))
    return iso


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #


def test_save_and_load_returns_equivalent_sklearn_model(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    """Loading a saved sklearn model must predict identically to the original."""
    X_probe = np.array([[0.1, 0.2, 0.3], [-0.5, 0.0, 1.0]])
    expected = trained_gbr.predict(X_probe)

    registry.save(
        season=2026,
        round_num=6,
        models={"gbr": trained_gbr},
        metadata={"hyperparams": {"n_estimators": 20}, "train_mae": 0.12},
    )
    loaded = registry.load(2026, 6)

    assert set(loaded.keys()) == {"gbr", "metadata"}
    np.testing.assert_array_equal(loaded["gbr"].predict(X_probe), expected)


def test_save_persists_metadata_with_provenance_fields(
    registry: ModelRegistry, fitted_isotonic: IsotonicRegression
) -> None:
    """The save() call enriches user metadata with standard provenance."""
    registry.save(
        season=2025,
        round_num=12,
        models={"isotonic_win": fitted_isotonic},
        metadata={"train_mae": 0.18, "feature_cols": ["a", "b"]},
    )
    metadata_path = registry.root / "2025_round_12" / "metadata.json"
    assert metadata_path.exists()
    with metadata_path.open() as fh:
        meta = json.load(fh)

    # User-provided fields are preserved
    assert meta["train_mae"] == 0.18
    assert meta["feature_cols"] == ["a", "b"]
    # Provenance fields are auto-attached
    assert meta["season"] == 2025
    assert meta["round"] == 12
    assert meta["artifacts"] == ["isotonic_win"]
    assert "savedAt" in meta
    assert "pythonVersion" in meta
    assert "gitSha" in meta  # value is implementation-defined; presence is the contract


def test_multiple_artifacts_round_trip(
    registry: ModelRegistry,
    trained_gbr: GradientBoostingRegressor,
    fitted_isotonic: IsotonicRegression,
) -> None:
    """A typical round has GBR + XGB-like + isotonics; all must round-trip."""
    second_gbr = GradientBoostingRegressor(n_estimators=10, max_depth=2, random_state=1)
    second_gbr.fit(np.array([[0.0], [1.0], [2.0]]), np.array([0.0, 1.0, 2.0]))

    registry.save(
        season=2024,
        round_num=22,
        models={
            "gbr": trained_gbr,
            "xgb": second_gbr,  # not a real XGB, but covers the multi-artifact path
            "isotonic_win": fitted_isotonic,
        },
        metadata={"train_mae": 0.2},
    )
    loaded = registry.load(2024, 22)
    assert {"gbr", "xgb", "isotonic_win", "metadata"} == set(loaded.keys())


# --------------------------------------------------------------------------- #
# Query API
# --------------------------------------------------------------------------- #


def test_exists_reflects_save(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    assert not registry.exists(2026, 1)
    registry.save(2026, 1, {"gbr": trained_gbr}, {})
    assert registry.exists(2026, 1)
    assert not registry.exists(2026, 2)


def test_latest_returns_highest_round(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    assert registry.latest(2026) is None
    registry.save(2026, 3, {"gbr": trained_gbr}, {"phase": "third"})
    registry.save(2026, 7, {"gbr": trained_gbr}, {"phase": "seventh"})
    registry.save(2026, 5, {"gbr": trained_gbr}, {"phase": "fifth"})

    result = registry.latest(2026)
    assert result is not None
    round_num, metadata = result
    assert round_num == 7
    assert metadata["phase"] == "seventh"


def test_list_all_is_sorted_by_season_then_round(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    registry.save(2026, 2, {"gbr": trained_gbr}, {})
    registry.save(2025, 22, {"gbr": trained_gbr}, {})
    registry.save(2026, 1, {"gbr": trained_gbr}, {})

    entries = registry.list_all()
    keys = [(s, r) for s, r, _ in entries]
    assert keys == [(2025, 22), (2026, 1), (2026, 2)]


# --------------------------------------------------------------------------- #
# Idempotency & atomicity
# --------------------------------------------------------------------------- #


def test_resave_overwrites_cleanly(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    """Saving the same (season, round) twice produces only the latest content."""
    registry.save(2026, 1, {"gbr": trained_gbr}, {"version": "v1"})
    registry.save(2026, 1, {"gbr": trained_gbr}, {"version": "v2"})

    metadata = registry.load(2026, 1)["metadata"]
    assert metadata["version"] == "v2"

    # No leftover temp directories from the move
    leftovers = [p.name for p in registry.root.iterdir() if p.name.startswith(".")]
    assert leftovers == []


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("season", [1949, 2101, 0, -1])
def test_save_rejects_out_of_range_season(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor, season: int
) -> None:
    with pytest.raises(ValueError):
        registry.save(season, 1, {"gbr": trained_gbr}, {})


@pytest.mark.parametrize("round_num", [0, 100, -1, 9999])
def test_save_rejects_out_of_range_round(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor, round_num: int
) -> None:
    """Valid range is 1..99 — 1..30 covers real F1 calendars, 31..99 is
    reserved for sentinel entries (e.g. the race-pace ensemble at round=99
    trained on multi-season data)."""
    with pytest.raises(ValueError):
        registry.save(2026, round_num, {"gbr": trained_gbr}, {})


def test_save_accepts_sentinel_round_99(
    registry: ModelRegistry, trained_gbr: GradientBoostingRegressor
) -> None:
    """Sentinel round numbers (31..99) are valid for non-weekend entries."""
    registry.save(2026, 99, {"gbr": trained_gbr}, {"kind": "race-pace"})
    assert registry.exists(2026, 99)


def test_load_missing_round_raises(registry: ModelRegistry) -> None:
    with pytest.raises(FileNotFoundError):
        registry.load(2026, 99 if False else 7)  # never saved


# --------------------------------------------------------------------------- #
# Env-var gate
# --------------------------------------------------------------------------- #


def test_save_is_noop_when_disabled(
    registry: ModelRegistry,
    trained_gbr: GradientBoostingRegressor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REGISTRY_ENV_VAR, "0")
    assert not registry_enabled()
    result = registry.save(2026, 1, {"gbr": trained_gbr}, {})
    assert result is None
    assert not registry.exists(2026, 1)


@pytest.mark.parametrize("flag", ["1", "true", "True", "yes", "anything-else"])
def test_save_is_enabled_for_truthy_env_values(
    registry: ModelRegistry,
    trained_gbr: GradientBoostingRegressor,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
) -> None:
    monkeypatch.setenv(REGISTRY_ENV_VAR, flag)
    assert registry_enabled()
    registry.save(2026, 1, {"gbr": trained_gbr}, {})
    assert registry.exists(2026, 1)
