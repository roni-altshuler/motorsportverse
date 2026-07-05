"""Tests for the direct finishing-position model (models/position_model.py).

Covers the guarantees the export pipeline relies on:
- leakage guard (never trains on the target round or later),
- determinism (random_state=42 → identical predictions across fits),
- graceful degradation (< 3 prior rounds → no model / applied:false),
- modelConfig recording via the export reorder path,
- the A/B backtest output schema.
"""
from __future__ import annotations

import json

import pytest

from motorsport_core.leakage import LeakageError
from models.position_model import (
    FEATURE_NAMES,
    build_training_frame,
    extract_round_features,
    predicted_order,
    run_backtest,
    train_position_model,
)

DRIVERS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]


def _classification(order: list[str], *, base_time: float = 90.0) -> list[dict]:
    """Synthesise a committed-style classification list for a set of drivers.

    ``order`` is the predicted finishing order (position 1 first).  Fields mirror
    what ``round_NN.json::classification`` carries.
    """
    rows = []
    for i, drv in enumerate(order):
        pos = i + 1
        rows.append({
            "driver": drv,
            "position": pos,
            "predictedTime": round(base_time + i * 0.25, 3),
            "winProbability": round(max(0.0, 30.0 - i * 4), 1),
            "dnfProbability": round(0.08 + 0.01 * i, 4),
            "finishRangeLow": max(1, pos - 2),
            "finishRangeHigh": min(len(order), pos + 2),
        })
    return rows


def _actual(order: list[str]) -> dict[str, int]:
    return {drv: i + 1 for i, drv in enumerate(order)}


def _rot(seq: list[str], k: int) -> list[str]:
    return seq[k:] + seq[:k]


def _rounds_and_actuals(n_rounds: int):
    """Build n rounds of features + actuals with a stable-but-noisy relationship."""
    rounds_by_round = {}
    actual = {}
    for r in range(1, n_rounds + 1):
        pred_order = _rot(DRIVERS, r % len(DRIVERS))
        # Actual is the predicted order with a small perturbation (swap a pair).
        act_order = list(pred_order)
        if len(act_order) >= 4:
            act_order[2], act_order[3] = act_order[3], act_order[2]
        rounds_by_round[r] = _classification(pred_order)
        actual[r] = _actual(act_order)
    return rounds_by_round, actual


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #


def test_extract_round_features_shape():
    rows = _classification(DRIVERS)
    feats = extract_round_features(rows)
    assert set(feats) == set(DRIVERS)
    for f in feats.values():
        assert set(f) == set(FEATURE_NAMES)
    # Fastest predicted time → rank 1, zero gap.
    assert feats["AAA"]["predTimeRank"] == 1.0
    assert feats["AAA"]["predTimeGap"] == 0.0
    # Win probability normalised into [0, 1].
    assert 0.0 <= feats["AAA"]["winProbability"] <= 1.0


def test_extract_round_features_empty():
    assert extract_round_features([]) == {}


# --------------------------------------------------------------------------- #
# Leakage guard
# --------------------------------------------------------------------------- #


def test_build_training_frame_excludes_target_and_future():
    rounds_by_round, actual = _rounds_and_actuals(6)
    X, y, rounds_used = build_training_frame(rounds_by_round, actual, target_round=4)
    # Only rounds strictly before 4 may contribute.
    assert rounds_used == [1, 2, 3]
    assert X.shape[1] == len(FEATURE_NAMES)
    assert X.shape[0] == len(y)
    assert len(y) == 3 * len(DRIVERS)


def test_build_training_frame_leakage_guard_trips_on_bad_filter(monkeypatch):
    """If the internal prior-only filter is defeated, the assertion must fire."""
    import models.position_model as pm

    rounds_by_round, actual = _rounds_and_actuals(6)

    # Simulate a regression where the filter stops excluding the target round.
    real_assert = pm.assert_prior_only

    def _boom_if_target_present(rounds_map, current_round, label="x"):
        # Inject the target round to prove the assertion is load-bearing.
        leaky = dict(rounds_map)
        leaky[current_round] = []
        return real_assert(leaky, current_round=current_round, label=label)

    monkeypatch.setattr(pm, "assert_prior_only", _boom_if_target_present)
    with pytest.raises(LeakageError):
        build_training_frame(rounds_by_round, actual, target_round=4)


# --------------------------------------------------------------------------- #
# Determinism + graceful degradation
# --------------------------------------------------------------------------- #


def test_training_is_deterministic():
    rounds_by_round, actual = _rounds_and_actuals(6)
    m1 = train_position_model(rounds_by_round, actual, target_round=6, min_prior_rounds=3)
    m2 = train_position_model(rounds_by_round, actual, target_round=6, min_prior_rounds=3)
    assert m1 is not None and m2 is not None
    feats = extract_round_features(rounds_by_round[6])
    p1 = m1.predict_positions(feats)
    p2 = m2.predict_positions(feats)
    assert p1 == p2
    # And the derived order is deterministic too.
    assert predicted_order(p1) == predicted_order(p2)


def test_graceful_degradation_too_few_rounds():
    rounds_by_round, actual = _rounds_and_actuals(2)
    model = train_position_model(rounds_by_round, actual, target_round=3, min_prior_rounds=3)
    assert model is None


def test_predicted_order_is_a_permutation():
    rounds_by_round, actual = _rounds_and_actuals(6)
    model = train_position_model(rounds_by_round, actual, target_round=6, min_prior_rounds=3)
    feats = extract_round_features(rounds_by_round[6])
    order = predicted_order(model.predict_positions(feats))
    assert sorted(order) == sorted(DRIVERS)


# --------------------------------------------------------------------------- #
# A/B backtest
# --------------------------------------------------------------------------- #


def test_run_backtest_schema_and_degradation():
    rounds_by_round, actual = _rounds_and_actuals(6)
    result = run_backtest(2026, rounds_by_round, actual, min_prior_rounds=3)
    assert result["season"] == 2026
    assert result["roundsScored"] == 6
    # Rounds 1-3 lack >=3 priors → applied:false; 4-6 apply.
    applied = {r["round"]: r["positionModel"]["applied"] for r in result["rounds"]}
    assert applied[1] is False and applied[3] is False
    assert applied[4] is True and applied[6] is True
    assert result["roundsCompared"] == 3
    # Every round has a production score.
    for r in result["rounds"]:
        assert "production" in r
    # Walk-forward blocks present for both heads.
    assert "positionModel" in result["walkForward"]
    assert "production" in result["walkForward"]
    assert result["verdict"]["recommendation"] in {
        "position-model-better", "production-better", "inconclusive",
    }
    # Serialisable.
    json.dumps(result)


# --------------------------------------------------------------------------- #
# Export wiring: modelConfig recording + reorder
# --------------------------------------------------------------------------- #


@pytest.fixture()
def _export_module(monkeypatch, tmp_path):
    """Import export_website_data with rounds/results globals pointed at tmp."""
    import export_website_data as m

    rounds_dir = tmp_path / "rounds"
    rounds_dir.mkdir()
    rounds_by_round, actual = _rounds_and_actuals(5)
    for r, rows in rounds_by_round.items():
        (rounds_dir / f"round_{r:02d}.json").write_text(
            json.dumps({"round": r, "classification": rows})
        )
    results_file = tmp_path / "season_results.json"
    results_file.write_text(json.dumps({str(r): v for r, v in actual.items()}))

    monkeypatch.setattr(m, "ROUNDS_DIR", str(rounds_dir))
    monkeypatch.setattr(m, "SEASON_RESULTS_FILE", str(results_file))
    return m, rounds_by_round, actual


def test_export_reorder_applies_and_records(_export_module):
    m, rounds_by_round, actual = _export_module
    # Predict round 6 (5 prior rounds available → applies).
    classification_data = [dict(e) for e in _classification(DRIVERS)]
    cfg = m._apply_position_model_reorder(
        classification_data, round_num=6, gp_key="Test", season=2026
    )
    assert cfg["applied"] is True
    assert cfg["minPriorRounds"] == 3
    assert set(cfg["features"]) == set(FEATURE_NAMES)
    # Positions reassigned 1..N with no gaps/dupes; points follow position.
    positions = [e["position"] for e in classification_data]
    assert positions == list(range(1, len(classification_data) + 1))
    assert classification_data[0]["gap"] == "LEADER"
    assert classification_data[0]["points"] >= classification_data[-1]["points"]
    # Driver set is preserved (nothing dropped).
    assert sorted(e["driver"] for e in classification_data) == sorted(DRIVERS)


def test_export_reorder_degrades_when_too_few_rounds(_export_module):
    m, _, _ = _export_module
    classification_data = [dict(e) for e in _classification(DRIVERS)]
    before = [e["driver"] for e in classification_data]
    # Round 3 → only 2 prior rounds → not applied, order untouched.
    cfg = m._apply_position_model_reorder(
        classification_data, round_num=3, gp_key="Test", season=2026
    )
    assert cfg["applied"] is False
    assert "reason" in cfg
    assert [e["driver"] for e in classification_data] == before
