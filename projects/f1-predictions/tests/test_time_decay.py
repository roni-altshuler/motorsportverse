"""Tests for exponential time-decay sample weighting."""
from __future__ import annotations

import pytest

from models.time_decay import (
    compute_sample_weights,
    round_decay_weight,
)


def test_round_decay_current_round_is_one():
    assert round_decay_weight(2026, 5, 2026, 5, half_life_rounds=8.0) == 1.0


def test_round_decay_one_halflife_back():
    # 8 rounds back → weight 0.5.
    w = round_decay_weight(2026, 1, 2026, 9, half_life_rounds=8.0)
    assert w == pytest.approx(0.5)


def test_round_decay_two_halflife_back():
    w = round_decay_weight(2025, 16, 2026, 10, half_life_rounds=8.0)
    # Age = (1 * 22) + (10 - 16) = 16 rounds. 16/8 = 2 → 0.25.
    assert w == pytest.approx(0.25)


def test_round_decay_rejects_nonpositive_halflife():
    with pytest.raises(ValueError, match="half_life_rounds"):
        round_decay_weight(2026, 1, 2026, 5, half_life_rounds=0)


def test_round_decay_future_row_clamped():
    # A "future" row shouldn't be amplified — it gets weight 1.0.
    assert round_decay_weight(2026, 9, 2026, 5, half_life_rounds=8.0) == 1.0


def test_sample_weights_normalize_to_unit_mean():
    seasons = [2024, 2025, 2026, 2026]
    rounds = [10, 5, 1, 3]
    w = compute_sample_weights(
        seasons,
        rounds,
        current_season=2026,
        current_round=5,
        half_life_rounds=8.0,
        era_mode="exponential",
        era_decay=0.5,
    )
    assert w.shape == (4,)
    assert w.mean() == pytest.approx(1.0)


def test_sample_weights_recent_rows_heavier_than_old():
    seasons = [2024, 2026]
    rounds = [1, 1]
    w = compute_sample_weights(
        seasons,
        rounds,
        current_season=2026,
        current_round=5,
        normalize=False,
    )
    # 2026 row is closer in time AND era → strictly heavier.
    assert w[1] > w[0]


def test_sample_weights_hard_cut_zeroes_distant_eras():
    seasons = [2019, 2026]
    rounds = [10, 1]
    w = compute_sample_weights(
        seasons,
        rounds,
        current_season=2026,
        current_round=5,
        era_mode="hard_cut",
        era_hard_cut=1,
        normalize=False,
    )
    # 2019 is two eras back → era_decay_factor=0 → weight clipped to min_weight, not 0.
    assert w[0] < w[1]


def test_sample_weights_min_weight_floor_applied():
    """Even far-back rows should not be exactly zero unless caller asks."""
    seasons = [2019]
    rounds = [1]
    w = compute_sample_weights(
        seasons,
        rounds,
        current_season=2026,
        current_round=5,
        era_mode="hard_cut",
        era_hard_cut=0,
        min_weight=1e-3,
        normalize=False,
    )
    assert w[0] == pytest.approx(1e-3)


def test_sample_weights_empty_input():
    w = compute_sample_weights(
        [], [], current_season=2026, current_round=1
    )
    assert w.shape == (0,)


def test_sample_weights_shape_mismatch_raises():
    with pytest.raises(ValueError, match="same length"):
        compute_sample_weights(
            [2025, 2026], [1], current_season=2026, current_round=2
        )
