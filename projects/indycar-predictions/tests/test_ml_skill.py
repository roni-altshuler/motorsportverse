"""Optional gradient-boosted skill signal: gates, degradation, real fit."""
from __future__ import annotations

from indycar_predictions import config, ml_skill, model

SEASON = config.SEASON


def test_ml_skill_none_before_training_window(real_source):
    stack = model._elo_skill(real_source, 2018, 10)
    out = ml_skill.predict_ml_skill(
        real_source, 2018, list(range(1, 10)), stack["driver"], 13.0
    )
    assert out is None  # 2018 < ML_FIRST_SEASON (2019)


def test_ml_skill_none_with_too_few_rounds(real_source):
    out = ml_skill.predict_ml_skill(real_source, SEASON, [1], {}, 13.0)
    assert out is None


def test_ml_skill_none_when_disabled(real_source, monkeypatch):
    monkeypatch.setattr(config, "USE_ML_SKILL", False)
    out = ml_skill.predict_ml_skill(
        real_source, SEASON, list(range(1, 9)), {}, 13.0
    )
    assert out is None


def test_ml_skill_predicts_for_full_roster(real_source):
    prior = list(range(1, 9))
    stack = model._elo_skill(real_source, SEASON, 9)
    out = ml_skill.predict_ml_skill(
        real_source, SEASON, prior, stack["driver"], 13.0, track_type="oval"
    )
    assert out is not None
    roster = {d["code"] for d in real_source.roster(SEASON)}
    assert roster <= set(out)
    # Predicted mean finishing positions live on a sane scale.
    assert all(0.0 < v < 40.0 for v in out.values())
    # Deterministic (seeded learners, OMP_NUM_THREADS pinned in CI).
    out2 = ml_skill.predict_ml_skill(
        real_source, SEASON, prior, stack["driver"], 13.0, track_type="oval"
    )
    assert out == out2


def test_track_type_interaction_feature(real_source):
    """The oval/road-street specialist signal must be present in the frame."""
    stack = model._elo_skill(real_source, SEASON, 9)
    rows = ml_skill._per_driver_features(
        real_source, SEASON, list(range(1, 9)), stack["driver"], 13.0, "oval"
    )
    assert "track_type_split" in ml_skill.FEATURE_COLUMNS
    splits = [r["track_type_split"] for r in rows.values()]
    assert any(abs(s) > 0.5 for s in splits)  # real specialists exist
