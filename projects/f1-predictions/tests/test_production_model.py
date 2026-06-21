"""Tests for the Phase-10 production model facade."""
from __future__ import annotations

import os

import pandas as pd
import pytest

from models.production_model import (
    FEATURE_FLAG_ENV,
    PRODUCTION_MODEL_VARIANT,
    PRODUCTION_MODEL_VERSION,
    ProductionPrediction,
    is_enabled,
)


# --------------------------------------------------------------------------- #
# Feature flag
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolate_env():
    """Save / restore the env var around each test."""
    saved = os.environ.pop(FEATURE_FLAG_ENV, None)
    yield
    os.environ.pop(FEATURE_FLAG_ENV, None)
    if saved is not None:
        os.environ[FEATURE_FLAG_ENV] = saved


def test_flag_defaults_to_disabled_when_unset() -> None:
    os.environ.pop(FEATURE_FLAG_ENV, None)
    assert is_enabled() is False


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "anything_else"])
def test_flag_disabled_for_falsy_values(value: str) -> None:
    os.environ[FEATURE_FLAG_ENV] = value
    assert is_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", "on"])
def test_flag_enabled_for_truthy_values(value: str) -> None:
    os.environ[FEATURE_FLAG_ENV] = value
    assert is_enabled() is True


# --------------------------------------------------------------------------- #
# Schema invariants
# --------------------------------------------------------------------------- #


def test_version_string_well_formed() -> None:
    assert isinstance(PRODUCTION_MODEL_VERSION, str)
    assert len(PRODUCTION_MODEL_VERSION) >= 8


def test_variant_string_matches_registered_name() -> None:
    """The variant string must match a real entry in benchmark_models.VARIANTS."""
    from benchmark_models import VARIANTS
    assert PRODUCTION_MODEL_VARIANT in VARIANTS


def test_prediction_dataclass_is_frozen() -> None:
    """ProductionPrediction is dataclass(frozen=True) — attributes can't be mutated."""
    pred = ProductionPrediction(
        season=2026,
        round=1,
        drivers=("VER", "HAM"),
        predicted_positions=(1, 2),
    )
    with pytest.raises(Exception):
        # frozen dataclass raises FrozenInstanceError (a TypeError subclass).
        pred.season = 2027  # type: ignore[misc]


def test_prediction_defaults_use_version_constants() -> None:
    pred = ProductionPrediction(
        season=2026, round=1,
        drivers=("VER",), predicted_positions=(1,),
    )
    assert pred.model_version == PRODUCTION_MODEL_VERSION
    assert pred.model_variant == PRODUCTION_MODEL_VARIANT


# --------------------------------------------------------------------------- #
# Determinism — the underlying variant called twice with identical inputs
# must return identical outputs.
# --------------------------------------------------------------------------- #


def _build_minimal_frame_chain(n_prior: int):
    """Construct a small prior chain of RoundFrame objects for a determinism
    test. Uses real Bahrain-2024-style integer ranks so the call exercises
    the regime-routed path without external dependencies."""
    from benchmark_models import RoundFrame
    from models.track_archetype import get_archetype

    drivers = [f"D{i:02d}" for i in range(1, 21)]
    frames = []
    for r in range(1, n_prior + 2):
        df = pd.DataFrame({
            "driver": drivers,
            "predicted": list(range(1, 21)),
            "actual": list(range(1, 21)),
            "predicted_lap_time": [90.0 + i * 0.1 for i in range(20)],
        })
        frames.append(
            RoundFrame(
                season=2024,
                round=r,
                gp_key="Bahrain",
                archetype=get_archetype("Bahrain"),
                df=df,
            )
        )
    return frames


def test_predict_for_round_is_deterministic() -> None:
    """Calling predict_for_round twice with identical inputs returns the
    same ranks and same metadata."""
    from models.production_model import predict_for_round

    frames = _build_minimal_frame_chain(n_prior=10)
    target = frames[-1]
    prior = frames[:-1]

    a = predict_for_round(target, prior)
    b = predict_for_round(target, prior)
    assert a.predicted_positions == b.predicted_positions
    assert a.drivers == b.drivers
    assert a.season == b.season == target.season
    assert a.round == b.round == target.round
    assert a.model_version == b.model_version == PRODUCTION_MODEL_VERSION


def test_predict_returns_one_position_per_driver() -> None:
    from models.production_model import predict_for_round

    frames = _build_minimal_frame_chain(n_prior=10)
    pred = predict_for_round(frames[-1], frames[:-1])
    assert len(pred.predicted_positions) == len(pred.drivers)
    # Each driver gets a distinct rank from 1..N.
    assert sorted(pred.predicted_positions) == list(range(1, len(pred.drivers) + 1))
