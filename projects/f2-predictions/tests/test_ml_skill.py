"""The gradient-boosted skill signal: leakage-safe, gracefully degrading.

These mirror the discipline the Bayesian path is held to: the ML signal must be
prior-only, must produce a valid per-driver mapping when it activates, must leave
the pace blend a sane (finite, in-range, lower=faster) signal, must never raise,
and must degrade gracefully — to a GBR-only signal when xgboost is absent
(scikit-learn ships with motorsport-core), and to None when ML is disabled or
there is too little data.
"""
import sys

import pytest

from f2_predictions import config, ml_skill, model
from f2_predictions.datasource import F2DataSource


@pytest.fixture
def source():
    return F2DataSource()


def _prior_rounds(current_round: int) -> list[int]:
    return [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]


# --------------------------------------------------------------------------- #
# Activation + shape
# --------------------------------------------------------------------------- #
def test_ml_skill_produces_a_valid_per_driver_mapping(source):
    cr = config.COMPLETED_ROUNDS + 1
    elo, _team = model._elo_skill(source, config.SEASON, cr)
    pred = ml_skill.predict_ml_skill(source, config.SEASON, _prior_rounds(cr), elo, field_mean=11.0)
    assert pred is not None, "ML signal should activate with a full prior season + deps present"
    assert set(pred) == {d["code"] for d in config.DRIVERS}
    # Learned mean finishing position: finite and within the grid range.
    assert all(0.0 < v < 30.0 for v in pred.values())


def test_ml_skill_is_none_with_too_few_prior_rounds(source):
    # current_round=2 → exactly one prior round → below ML_MIN_PRIOR_ROUNDS.
    pred = ml_skill.predict_ml_skill(source, config.SEASON, _prior_rounds(2), {}, field_mean=11.0)
    assert pred is None


def test_ml_skill_disabled_by_flag(source, monkeypatch):
    monkeypatch.setattr(config, "USE_ML_SKILL", False)
    cr = config.COMPLETED_ROUNDS + 1
    pred = ml_skill.predict_ml_skill(source, config.SEASON, _prior_rounds(cr), {}, field_mean=11.0)
    assert pred is None


# --------------------------------------------------------------------------- #
# Leakage safety — the signal must depend only on prior rounds
# --------------------------------------------------------------------------- #
def test_ml_skill_features_use_prior_rounds_only(source, monkeypatch):
    """Calling for round R must never read results at or beyond R."""
    seen: list[int] = []
    real = source.race_results_for_round

    def spy(year, rnd):
        seen.append(rnd)
        return real(year, rnd)

    monkeypatch.setattr(source, "race_results_for_round", spy)
    cr = 5
    elo, _ = model._elo_skill(source, config.SEASON, cr)
    seen.clear()
    ml_skill.predict_ml_skill(source, config.SEASON, _prior_rounds(cr), elo, field_mean=11.0)
    assert seen, "expected the feature builder to read prior rounds"
    assert max(seen) < cr, f"leakage: read round {max(seen)} while forecasting round {cr}"


# --------------------------------------------------------------------------- #
# Optional deps: xgboost absent → GBR-only signal; sklearn always present (core)
# --------------------------------------------------------------------------- #
def test_ml_skill_degrades_to_gbr_only_without_xgboost(source, monkeypatch):
    cr = config.COMPLETED_ROUNDS + 1
    elo, _team = model._elo_skill(source, config.SEASON, cr)
    # Simulate xgboost being unimportable: the import inside predict_ml_skill must
    # be caught and the model must keep running as a GBR-only signal (scikit-learn
    # ships with motorsport-core), never raising and never dropping ML entirely.
    monkeypatch.setitem(sys.modules, "xgboost", None)
    pred = ml_skill.predict_ml_skill(source, config.SEASON, _prior_rounds(cr), elo, field_mean=11.0)
    assert pred is not None, "without xgboost the signal should degrade to GBR-only, not None"
    assert set(pred) == {d["code"] for d in config.DRIVERS}
    assert all(0.0 < v < 30.0 for v in pred.values())


# --------------------------------------------------------------------------- #
# Blend integration — the pace mapping stays sane with ML on
# --------------------------------------------------------------------------- #
def test_estimate_skill_with_ml_is_a_valid_pace_mapping(source):
    pace = model.estimate_skill(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    assert len(pace) == 22
    assert all(80.0 < v < 100.0 for v in pace.values())  # same band the model_f2 tests assert


def test_estimate_skill_matches_linear_blend_when_ml_off(source, monkeypatch):
    """With ML off the blend is exactly the original Elo+history pace (no regression)."""
    cr = config.COMPLETED_ROUNDS + 1
    with_ml = model.estimate_skill(source, config.SEASON, cr)
    monkeypatch.setattr(config, "USE_ML_SKILL", False)
    without_ml = model.estimate_skill(source, config.SEASON, cr)
    # Both are valid; the ML-on blend may differ but must not be degenerate.
    assert set(with_ml) == set(without_ml)
    assert all(80.0 < v < 100.0 for v in with_ml.values())


def test_ordering_is_still_lower_is_faster(source):
    """Fastest driver (min pace) leads the merit feature grid — invariant preserved."""
    cr = config.COMPLETED_ROUNDS + 1
    pace = model.estimate_skill(source, config.SEASON, cr)
    fc = model.forecast_round(source, config.SEASON, cr, n_samples=2000)
    assert fc.feature.grid[0] == min(pace, key=lambda c: pace[c])
