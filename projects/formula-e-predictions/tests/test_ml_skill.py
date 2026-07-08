"""Gradient-boosted skill signal: gates, era window, determinism."""
from __future__ import annotations

from formula_e_predictions import config, ml_skill, model

SEASON = config.SEASON


def _elo(real_source, rnd):
    driver_elo, _team, _career = model._elo_skill(real_source, SEASON, rnd)
    return driver_elo


def test_returns_none_below_min_prior_rounds(real_source):
    elo = _elo(real_source, 2)
    assert ml_skill.predict_ml_skill(real_source, SEASON, [1], elo, 10.0) is None


def test_returns_none_before_gen3_window(real_source):
    """Pre-Gen3 seasons never train the learned signal (Elo/era priors only)."""
    elo = {d["code"]: 1500.0 for d in real_source.roster(2022)}
    assert ml_skill.predict_ml_skill(real_source, 2022, [1, 2, 3], elo, 11.0) is None


def test_returns_none_when_flag_off(real_source, monkeypatch):
    monkeypatch.setattr(config, "USE_ML_SKILL", False)
    elo = _elo(real_source, 4)
    assert ml_skill.predict_ml_skill(real_source, SEASON, [1, 2, 3], elo, 10.0) is None


def test_predicts_for_full_roster_and_is_deterministic(real_source):
    elo = _elo(real_source, 4)
    prior = [1, 2, 3]
    a = ml_skill.predict_ml_skill(real_source, SEASON, prior, elo, 10.5)
    b = ml_skill.predict_ml_skill(real_source, SEASON, prior, elo, 10.5)
    assert a is not None
    assert set(a) == {d["code"] for d in config.DRIVERS}
    assert a == b
    # Lower = faster: predictions live on the finishing-position scale.
    assert all(0.0 < v < 25.0 for v in a.values())


def test_feature_columns_stable():
    """The scaler/learner matrix contract — reordering breaks saved intuition."""
    assert ml_skill.FEATURE_COLUMNS == [
        "roll_mean_finish",
        "roll_median_finish",
        "form_trend",
        "grid_finish_delta",
        "teammate_delta",
        "driver_elo",
        "rookie_flag",
        "street_circuit_split",
    ]
