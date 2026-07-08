"""Position-head tests: gate, leakage, graceful degradation, A/B backtest."""
from __future__ import annotations

import numpy as np

from formula_e_predictions import config, model, position_head

SEASON = config.SEASON


# --------------------------------------------------------------------------- #
# Gate
# --------------------------------------------------------------------------- #
def test_gate_default_off(monkeypatch):
    monkeypatch.delenv(position_head.ENV_FLAG, raising=False)
    assert position_head.head_enabled() is False
    assert position_head.head_enabled(True) is True
    assert position_head.head_enabled(False) is False


def test_gate_env_flag(monkeypatch):
    monkeypatch.setenv(position_head.ENV_FLAG, "1")
    assert position_head.head_enabled() is True
    monkeypatch.setenv(position_head.ENV_FLAG, "off")
    assert position_head.head_enabled() is False


def test_production_forecast_ignores_head_by_default(truncated_source, monkeypatch):
    monkeypatch.delenv(position_head.ENV_FLAG, raising=False)
    fc = model.forecast_round(truncated_source, SEASON, 4)
    assert fc.position_head is None


# --------------------------------------------------------------------------- #
# Features + frame
# --------------------------------------------------------------------------- #
def test_extract_race_features(truncated_source):
    fc = model.forecast_round(truncated_source, SEASON, 4, use_position_head=False)
    feats = position_head.extract_race_features(fc.race, venue_kind=fc.venue_kind)
    assert set(feats) == set(fc.race.score)
    for f in feats.values():
        assert set(f) == set(position_head.FEATURE_NAMES)
    ranks = sorted(f["scoreRank"] for f in feats.values())
    assert ranks == list(range(1, len(feats) + 1))


def test_training_frame_is_prior_only(truncated_source):
    fc4 = model.forecast_round(truncated_source, SEASON, 4, use_position_head=False)
    actual4 = {r.competitor: r.position for r in truncated_source.results(SEASON, 4)}
    # The target round (and anything later) never contributes a training row —
    # it is filtered before assembly and the leakage assert double-checks.
    X, y, used = position_head.build_training_frame(
        {4: fc4, 5: fc4}, {4: actual4, 5: actual4}, target_round=4
    )
    assert used == [] and len(X) == len(y) == 0
    # Strictly-prior rounds assemble cleanly.
    X, y, used = position_head.build_training_frame({3: fc4}, {3: actual4}, target_round=4)
    assert used == [3] and len(X) == len(y) > 0
    assert X.shape[1] == len(position_head.FEATURE_NAMES)


def test_train_for_round_degrades_below_min_priors(truncated_source):
    head = position_head.train_for_round(truncated_source, SEASON, 2, min_prior_rounds=3)
    assert head is None


def test_maybe_rerank_records_degradation(truncated_source):
    fc = model.forecast_round(truncated_source, SEASON, 2, use_position_head=False)
    out = position_head.maybe_rerank_round(
        truncated_source, SEASON, 2, fc, n_samples=500, min_prior_rounds=3
    )
    assert out.position_head == {
        "applied": False,
        "reason": "fewer than 3 prior completed rounds",
    }
    assert out.race.order == fc.race.order  # untouched


def test_maybe_rerank_applies_with_enough_priors(truncated_source):
    fc = model.forecast_round(truncated_source, SEASON, 5, use_position_head=False)
    out = position_head.maybe_rerank_round(
        truncated_source, SEASON, 5, fc, n_samples=500, min_prior_rounds=3
    )
    assert out.position_head["applied"] is True
    assert out.position_head["trainedRounds"] == [1, 2, 3, 4]
    assert sorted(out.race.order) == sorted(fc.race.order)  # same drivers, re-ranked
    assert out.race.grid == fc.race.grid                    # grid never changes


def test_head_fit_predict_deterministic():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, len(position_head.FEATURE_NAMES)))
    y = rng.uniform(1, 20, size=60)
    feats = {
        f"D{i}": dict(zip(position_head.FEATURE_NAMES, X[i])) for i in range(10)
    }
    p1 = position_head.PositionHead().fit(X, y).predict_positions(feats)
    p2 = position_head.PositionHead().fit(X, y).predict_positions(feats)
    assert p1 == p2


def test_run_backtest_shapes(truncated_source):
    result = position_head.run_backtest(truncated_source, SEASON, min_prior_rounds=3)
    assert result["roundsScored"] == 5
    assert result["roundsCompared"] == 2  # rounds 4 and 5 have >= 3 priors
    verdict = result["verdict"]
    assert verdict["recommendation"] in (
        "position-head-better", "production-better", "inconclusive",
    )
    applied = [r for r in result["rounds"] if r["positionHead"].get("applied")]
    assert len(applied) == 2
    for entry in applied:
        assert "race" in entry["positionHead"]
        sanity = entry["positionHead"]["monotonicSanity"]
        # The head re-ranks around the pace signal — never inverts it.
        assert sanity is None or sanity > 0.0
