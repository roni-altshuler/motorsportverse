"""Tests for driver/team Elo + EloFeatureBuilder."""
from __future__ import annotations

import pytest

from motorsport_core.elo import (
    DEFAULT_RATING,
    K_PROVISIONAL,
    K_SETTLED,
    DriverElo,
    EloFeatureBuilder,
    RaceEvent,
    TeamElo,
    expected_score,
    k_factor_for_experience,
)


def test_expected_score_symmetry():
    # Equal rating → 50/50.
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    # 400 points up → ≈ 0.91.
    assert expected_score(1900, 1500) == pytest.approx(0.9090909, rel=1e-4)


def test_k_factor_schedule():
    assert k_factor_for_experience(0) == K_PROVISIONAL
    assert k_factor_for_experience(9) == K_PROVISIONAL
    assert k_factor_for_experience(10) == 25.0
    assert k_factor_for_experience(35) == K_SETTLED


def test_driver_elo_winner_gains_loser_drops():
    elo = DriverElo()
    elo.update_pairwise("A", "B", 1.0, 2026, 1)
    assert elo.rating("A") > DEFAULT_RATING
    assert elo.rating("B") < DEFAULT_RATING
    # Zero-sum (within float).
    assert (elo.rating("A") - DEFAULT_RATING) + (
        elo.rating("B") - DEFAULT_RATING
    ) == pytest.approx(0.0)


def test_team_elo_damped_relative_to_driver():
    drv = DriverElo()
    team = TeamElo()
    drv.update_pairwise("A", "B", 1.0, 2026, 1)
    team.update_pairwise("Red", "Blue", 1.0, 2026, 1)
    drv_gain = drv.rating("A") - DEFAULT_RATING
    team_gain = team.rating("Red") - DEFAULT_RATING
    assert team_gain == pytest.approx(drv_gain * team.k_damping)


def test_initialise_rookie_falls_back_to_league_mean_without_team_history():
    elo = DriverElo()
    elo.initialise_rookie("Rookie", "EmptyTeam", team_to_driver_ratings={})
    assert elo.rating("Rookie") == DEFAULT_RATING - 25.0


def test_initialise_rookie_pulls_from_team_mean_when_available():
    elo = DriverElo()
    # Pretend team had two rated drivers at 1600 and 1700.
    elo.initialise_rookie(
        "Rookie", "Mercedes",
        team_to_driver_ratings={"Mercedes": [1600.0, 1700.0]},
    )
    # 1650 - 25 discount.
    assert elo.rating("Rookie") == pytest.approx(1625.0)


def test_inter_season_decay_pulls_toward_league_mean():
    elo = DriverElo(inter_season_shrink=0.5, era_boundary_shrink=0.5)
    # Boost A to 1900, anchor in 2024.
    elo.update_pairwise("A", "B", 1.0, 2024, 1, k_override=400.0)
    pre = elo.rating("A")
    assert pre > 1500.0
    # Now apply a 2026 event — same era ≠ 2024 ⇒ decay applied. (era_distance > 0
    # forces era_boundary_shrink; both 0.5 here.)
    elo.update_pairwise("A", "B", 0.5, 2026, 1)
    post = elo.rating("A")
    # post should be smaller than pre (decay pulled toward 1500).
    assert post < pre


def test_replay_history_rejects_leakage():
    builder = EloFeatureBuilder()
    events = [
        RaceEvent(
            season=2026,
            round=2,
            finish_order={"VER": 1, "NOR": 2, "PIA": 3},
            grid_order={"VER": 1, "NOR": 3, "PIA": 2},
            team_of={"VER": "RBR", "NOR": "MCL", "PIA": "MCL"},
        ),
    ]
    with pytest.raises(ValueError, match="leakage"):
        builder.replay_history(events, current_season=2026, current_round=2)


def test_feature_builder_produces_seven_features():
    builder = EloFeatureBuilder()
    event_a = RaceEvent(
        season=2026,
        round=1,
        finish_order={"VER": 1, "NOR": 2, "PIA": 3, "HAM": 4},
        grid_order={"VER": 1, "NOR": 3, "PIA": 2, "HAM": 4},
        team_of={"VER": "RBR", "NOR": "MCL", "PIA": "MCL", "HAM": "FER"},
        wet=False,
    )
    event_b = RaceEvent(
        season=2026,
        round=2,
        finish_order={"VER": 2, "NOR": 1, "PIA": 4, "HAM": 3},
        grid_order={"VER": 1, "NOR": 2, "PIA": 3, "HAM": 4},
        team_of={"VER": "RBR", "NOR": "MCL", "PIA": "MCL", "HAM": "FER"},
        wet=True,
    )
    builder.replay_history([event_a, event_b], current_season=2026, current_round=3)
    features = builder.features_for("NOR", "MCL", teammate="PIA")
    assert set(features.keys()) == {
        "driver_elo",
        "team_elo",
        "driver_form_elo",
        "wet_weather_elo",
        "qualifying_elo",
        "racecraft_elo",
        "teammate_delta_elo",
    }
    # NOR finished ahead of PIA in both races → teammate delta should be > 0.
    assert features["teammate_delta_elo"] > 0


def test_feature_builder_chronological_order_strict():
    builder = EloFeatureBuilder()
    out_of_order = RaceEvent(
        season=2026,
        round=1,
        finish_order={"VER": 1, "NOR": 2},
        grid_order={"VER": 1, "NOR": 2},
        team_of={"VER": "RBR", "NOR": "MCL"},
    )
    builder.ingest_race(out_of_order)
    with pytest.raises(ValueError, match="chronological"):
        builder.ingest_race(out_of_order)


def test_ensure_rookies_seeds_new_drivers():
    builder = EloFeatureBuilder()
    # Existing rating for VER.
    builder.race_elo.update_pairwise("VER", "LEC", 1.0, 2025, 1)
    builder.race_elo.commit_race_attendance(["VER", "LEC"], 2025, 1)
    # Now Hadjar joins Racing Bulls in 2026.
    builder.ensure_rookies({"VER": "RBR", "HAD": "RBR", "LEC": "FER"})
    assert builder.race_elo.has("HAD")
    # HAD's rating uses team-mean fallback. RBR had only VER so should be ≈ VER - 25.
    assert builder.race_elo.rating("HAD") < builder.race_elo.rating("VER")
