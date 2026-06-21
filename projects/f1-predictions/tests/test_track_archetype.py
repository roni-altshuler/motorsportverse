"""Tests for the track archetype classifier."""
from __future__ import annotations

import pytest

from f1_prediction_utils import CALENDAR
from models.track_archetype import (
    ARCHETYPES,
    TrackArchetype,
    all_archetypes,
    get_archetype,
)


CIRCUIT_NAMES_FROM_2026 = [
    info["gp_key"] for info in CALENDAR.values()
]
CIRCUIT_NAMES_FROM_2026 += [info["circuit"] for info in CALENDAR.values()]
CIRCUIT_NAMES_FROM_2026 += [info["name"] for info in CALENDAR.values()]


@pytest.mark.parametrize("circuit_name", CIRCUIT_NAMES_FROM_2026)
def test_every_2026_circuit_resolves(circuit_name):
    """Every 2026 calendar circuit must resolve to an archetype."""
    a = get_archetype(circuit_name)
    assert a is not None, f"no archetype for 2026 calendar entry: {circuit_name!r}"
    assert isinstance(a, TrackArchetype)


def test_known_canonical_circuits():
    monaco = get_archetype("Monaco")
    assert monaco is not None
    assert monaco.archetype == "street_quali_locked"
    assert monaco.street_circuit is True

    monza = get_archetype("Italy")
    assert monza is not None
    assert monza.archetype == "power"
    assert monza.high_speed is True

    spain = get_archetype("Spain")
    assert spain is not None
    assert spain.archetype == "high_deg"

    bahrain = get_archetype("Bahrain")
    assert bahrain is not None
    assert bahrain.archetype == "high_variance"


def test_circuit_name_variants_resolve():
    # Singapore <-> Marina Bay
    a = get_archetype("Marina Bay")
    assert a is not None
    assert a.circuit_id == "singapore"
    # Belgium <-> Spa-Francorchamps
    a = get_archetype("Spa-Francorchamps")
    assert a is not None
    assert a.circuit_id == "spa"
    # Saudi -> jeddah
    a = get_archetype("Jeddah")
    assert a is not None
    assert a.circuit_id == "saudi"


def test_unknown_circuit_returns_none():
    assert get_archetype("Not a Circuit") is None
    assert get_archetype("") is None
    assert get_archetype(None) is None


@pytest.mark.parametrize("archetype", all_archetypes())
def test_floats_in_unit_range(archetype):
    for name in (
        "overtaking_difficulty",
        "qualifying_importance",
        "tire_deg_sensitivity",
        "safety_car_probability",
    ):
        v = getattr(archetype, name)
        assert 0.0 <= v <= 1.0, (
            f"{archetype.circuit_id}.{name}={v} out of [0,1]"
        )


@pytest.mark.parametrize("archetype", all_archetypes())
def test_archetype_label_in_known_set(archetype):
    assert archetype.archetype in ARCHETYPES


def test_archetypes_cover_all_known_labels():
    seen = {a.archetype for a in all_archetypes()}
    assert seen == set(ARCHETYPES), (
        f"expected archetype set {set(ARCHETYPES)} but seeded only {seen}"
    )
