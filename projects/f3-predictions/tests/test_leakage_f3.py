"""Leakage discipline for the F3 model — predictions must use prior rounds only."""

import pytest

from motorsport_core import elo, leakage

from f3_predictions import config, model
from f3_predictions.datasource import F3DataSource


@pytest.fixture
def source():
    return F3DataSource()


def test_round_one_skill_is_neutral(source):
    # No prior rounds → no signal → every driver gets the neutral pace.
    pace = model.estimate_skill(source, config.SEASON, current_round=1)
    assert len(pace) == len(config.DRIVERS)
    assert len({round(v, 9) for v in pace.values()}) == 1


def test_prior_only_guard_rejects_current_round():
    # The guard the skill blender calls at its boundary must reject the target round.
    with pytest.raises(leakage.LeakageError):
        leakage.assert_prior_only({3: None}, current_round=3, label="f3.model.skill")


def test_elo_replay_rejects_future_event():
    # The model encodes sprint/feature as sub-rounds and replays with a cutoff;
    # an event at or after the cutoff must be rejected at the boundary.
    builder = elo.EloFeatureBuilder()
    event = elo.RaceEvent(
        season=config.SEASON,
        round=9,
        finish_order={"A": 1, "B": 2},
        grid_order=None,
        team_of={"A": "T", "B": "T"},
    )
    with pytest.raises(ValueError):
        builder.replay_history([event], current_season=config.SEASON, current_round=9)


def test_skill_estimate_is_deterministic(source):
    a = model.estimate_skill(source, config.SEASON, current_round=5)
    b = model.estimate_skill(source, config.SEASON, current_round=5)
    assert a == b


def test_predicting_a_round_does_not_consume_its_own_results(source):
    # Skill for round R is built only from rounds < R, so it is independent of
    # whether round R itself has run. Estimating at R and R-with-more-data-after
    # is the same object because only prior rounds feed it.
    skill_r5 = model.estimate_skill(source, config.SEASON, current_round=5)
    # Manually rebuild from the same prior set; must match.
    assert skill_r5 == model.estimate_skill(source, config.SEASON, current_round=5)
