"""Optional gradient-boosted skill signal: gates, degradation, real fit."""
from __future__ import annotations

from nascar_predictions import config, ml_skill, model

SEASON = config.SEASON


def test_ml_skill_none_before_nextgen_window(real_source):
    stack = model._elo_skill(real_source, 2021, 10)
    out = ml_skill.predict_ml_skill(
        real_source, 2021, list(range(1, 10)), stack["driver"], 18.0
    )
    assert out is None


def test_ml_skill_none_with_too_few_rounds(real_source):
    out = ml_skill.predict_ml_skill(real_source, SEASON, [1], {}, 18.0)
    assert out is None


def test_ml_skill_none_when_disabled(real_source, monkeypatch):
    monkeypatch.setattr(config, "USE_ML_SKILL", False)
    out = ml_skill.predict_ml_skill(
        real_source, SEASON, list(range(1, 9)), {}, 18.0
    )
    assert out is None


def test_ml_skill_predicts_for_full_roster(real_source):
    prior = list(range(1, 9))
    stack = model._elo_skill(real_source, SEASON, 9)
    out = ml_skill.predict_ml_skill(
        real_source, SEASON, prior, stack["driver"], 18.0, track_type="short"
    )
    assert out is not None
    roster = {d["code"] for d in real_source.roster(SEASON)}
    assert roster <= set(out)
    # Predicted mean finishing positions live on a sane scale.
    assert all(0.0 < v < 45.0 for v in out.values())
    # Deterministic (seeded learners, OMP_NUM_THREADS pinned in CI).
    out2 = ml_skill.predict_ml_skill(
        real_source, SEASON, prior, stack["driver"], 18.0, track_type="short"
    )
    assert out == out2
