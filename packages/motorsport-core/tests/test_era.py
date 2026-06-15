"""Tests for the regulation-era lookup + decay helpers."""
from __future__ import annotations

import pytest

from motorsport_core.era import (
    ERAS,
    era_decay_factor,
    era_distance,
    era_of,
)


def test_era_of_known_season():
    assert era_of(2026).name == "active_aero_2026"
    assert era_of(2024).name == "ground_effect"
    assert era_of(2019).name == "wide_cars"


def test_era_of_open_ended_current_era():
    # The 2026 era has end_season=None, so future seasons resolve to it.
    assert era_of(2027).name == "active_aero_2026"


def test_era_of_rejects_pre_history():
    with pytest.raises(ValueError, match="older than"):
        era_of(2010)


def test_era_distance_symmetric():
    assert era_distance(2024, 2024) == 0
    assert era_distance(2024, 2026) == era_distance(2026, 2024) == 1
    assert era_distance(2019, 2026) == 2


def test_decay_exponential_default():
    assert era_decay_factor(2026, 2026, mode="exponential") == 1.0
    assert era_decay_factor(2024, 2026, mode="exponential") == pytest.approx(0.5)
    assert era_decay_factor(2019, 2026, mode="exponential") == pytest.approx(0.25)


def test_decay_hard_cut():
    # Within 1 era → 1.0; further → 0.0.
    assert era_decay_factor(2024, 2026, mode="hard_cut", hard_cut_eras=1) == 1.0
    assert era_decay_factor(2019, 2026, mode="hard_cut", hard_cut_eras=1) == 0.0
    # Wider cut admits the earlier era.
    assert era_decay_factor(2019, 2026, mode="hard_cut", hard_cut_eras=2) == 1.0


def test_decay_none_mode_is_passthrough():
    assert era_decay_factor(2014, 2026, mode="none") == 1.0


def test_decay_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unknown era-decay mode"):
        era_decay_factor(2024, 2026, mode="banana")


def test_eras_are_contiguous_and_ordered():
    for prev, nxt in zip(ERAS, ERAS[1:]):
        # No gap between successive eras.
        assert prev.end_season is not None
        assert prev.end_season + 1 == nxt.start_season
        # Strict ordering.
        assert prev.start_season < nxt.start_season
