"""Tests for the A/B-gated finishing-position head + walk-forward headline eval.

Port of the F1 flagship's position-model capability (commit 189db5b) to F2:
- the head is env-flag gated (``F2_USE_POSITION_HEAD``) and OFF by default —
  the production forecast must be byte-identical when the gate is closed;
- training is leakage-safe (prior rounds only, ``assert_prior_only`` at the
  boundary) and covers BOTH race types (reverse-grid sprint + merit feature);
- the walk-forward A/B backtest and the promotion gate are data-driven.
"""
from __future__ import annotations

import json

import pytest

from f2_predictions import config, forward_eval, model, position_head, promotion_decision
from f2_predictions.datasource import F2DataSource

SEASON = config.SEASON


@pytest.fixture(scope="module")
def source():
    return F2DataSource()


@pytest.fixture(scope="module")
def replay(source):
    """Shared leakage-safe replay of every completed round (head OFF)."""
    return position_head._prior_replays(source, SEASON, config.COMPLETED_ROUNDS + 1)


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    """forward_eval outputs + the position-head A/B artifact, generated once."""
    out = tmp_path_factory.mktemp("f2ab")
    fe_dir = out / "forward_eval"
    n = forward_eval.write(fe_dir, SEASON)
    assert n == config.COMPLETED_ROUNDS
    ab_path = forward_eval.run_position_head_ab(fe_dir, SEASON)
    assert ab_path is not None
    return out


# --------------------------------------------------------------------------- #
# The A/B gate
# --------------------------------------------------------------------------- #
def test_gate_is_off_by_default(monkeypatch):
    monkeypatch.delenv(position_head.ENV_FLAG, raising=False)
    assert position_head.head_enabled() is False


def test_gate_env_flag_and_override(monkeypatch):
    monkeypatch.setenv(position_head.ENV_FLAG, "1")
    assert position_head.head_enabled() is True
    # explicit override always wins over the environment
    assert position_head.head_enabled(False) is False
    monkeypatch.delenv(position_head.ENV_FLAG, raising=False)
    assert position_head.head_enabled(True) is True


def test_flag_off_production_path_unchanged(source, monkeypatch):
    monkeypatch.delenv(position_head.ENV_FLAG, raising=False)
    rnd = config.COMPLETED_ROUNDS
    fc_default = model.forecast_round(source, SEASON, rnd)
    fc_pinned = model.forecast_round(source, SEASON, rnd, use_position_head=False)
    assert fc_default.position_head is None
    assert fc_default.sprint.order == fc_pinned.sprint.order
    assert fc_default.feature.order == fc_pinned.feature.order
    assert fc_default.feature.markets.p_win == fc_pinned.feature.markets.p_win


def test_flag_on_reranks_both_races(source):
    rnd = config.COMPLETED_ROUNDS + 1  # enough prior rounds to train
    fc = model.forecast_round(source, SEASON, rnd, use_position_head=True)
    assert fc.position_head is not None and fc.position_head["applied"] is True
    assert fc.position_head["trainedRounds"] == list(range(1, config.COMPLETED_ROUNDS + 1))
    codes = {d["code"] for d in config.DRIVERS}
    for race in (fc.sprint, fc.feature):
        assert set(race.order) == codes and len(race.order) == len(codes)
        assert abs(sum(race.markets.p_win.values()) - 1.0) < 1e-6


def test_flag_on_degrades_gracefully_without_priors(source):
    fc = model.forecast_round(source, SEASON, 1, use_position_head=True)
    assert fc.position_head is not None and fc.position_head["applied"] is False
    baseline = model.forecast_round(source, SEASON, 1, use_position_head=False)
    assert fc.feature.order == baseline.feature.order  # production path intact


# --------------------------------------------------------------------------- #
# Features + training frame (leakage-safe, both race types)
# --------------------------------------------------------------------------- #
def test_extract_race_features_shapes(replay):
    forecasts, _ = replay
    fc = forecasts[config.COMPLETED_ROUNDS]
    for race, is_sprint in ((fc.sprint, 1.0), (fc.feature, 0.0)):
        feats = position_head.extract_race_features(race)
        assert set(feats) == set(race.score)
        best = min(race.score, key=race.score.get)
        assert feats[best]["scoreRank"] == 1.0
        assert feats[best]["scoreGap"] == 0.0
        for i, code in enumerate(race.grid, start=1):
            assert feats[code]["gridPosition"] == float(i)
        for row in feats.values():
            assert set(row) == set(position_head.FEATURE_NAMES)
            assert row["isSprint"] == is_sprint
            assert 0.0 <= row["winProbability"] <= 1.0


def test_training_frame_is_prior_only(replay):
    forecasts, actuals = replay
    target = 4
    X, y, rounds_used = position_head.build_training_frame(forecasts, actuals, target)
    assert rounds_used == [1, 2, 3]  # strictly < target even though 4,5 were supplied
    assert X.shape[1] == len(position_head.FEATURE_NAMES)
    assert X.shape[0] == len(y) > 0
    # finishers-only: every target is a real classified position
    assert all(1 <= p <= len(config.DRIVERS) for p in y)


def test_training_frame_pools_both_race_types(replay):
    forecasts, actuals = replay
    X, y, _ = position_head.build_training_frame(forecasts, actuals, 3)
    is_sprint_col = list(position_head.FEATURE_NAMES).index("isSprint")
    flags = set(X[:, is_sprint_col])
    assert flags == {0.0, 1.0}  # sprint AND feature rows present


def test_train_gate_and_determinism(source, replay):
    forecasts, actuals = replay
    # below the minimum prior rounds → graceful None
    assert position_head.train_for_round(
        source, SEASON, 1, forecasts_by_round=forecasts, actual_by_round=actuals
    ) is None
    assert position_head.train_for_round(
        source, SEASON, 2, forecasts_by_round=forecasts, actual_by_round=actuals
    ) is None
    head_a = position_head.train_for_round(
        source, SEASON, 3, forecasts_by_round=forecasts, actual_by_round=actuals
    )
    head_b = position_head.train_for_round(
        source, SEASON, 3, forecasts_by_round=forecasts, actual_by_round=actuals
    )
    assert head_a is not None and head_a.trained_rounds == [1, 2]
    feats = position_head.extract_race_features(forecasts[3].feature)
    pred_a = head_a.predict_positions(feats)
    pred_b = head_b.predict_positions(feats)
    assert pred_a == pred_b  # deterministic (random_state=42)
    sanity = position_head.monotonic_sanity(pred_a, feats)
    assert sanity is not None and sanity > 0  # re-ranks pace, never inverts it


# --------------------------------------------------------------------------- #
# Walk-forward A/B backtest
# --------------------------------------------------------------------------- #
def test_backtest_shape_and_verdict(data_dir):
    ab = json.loads((data_dir / "forward_eval" / "position_model_ab.json").read_text())
    assert ab["season"] == SEASON
    assert ab["roundsScored"] == config.COMPLETED_ROUNDS
    # min_prior_rounds=2 → rounds 1-2 are applied:false, 3..N compared
    assert ab["roundsCompared"] == config.COMPLETED_ROUNDS - 2
    for entry in ab["rounds"]:
        assert set(entry) >= {"round", "production", "positionHead"}
        for rt in ("sprint", "feature"):
            assert entry["production"][rt]["n"] > 0
        if entry["round"] <= 2:
            assert entry["positionHead"]["applied"] is False
        else:
            assert entry["positionHead"]["applied"] is True
            assert entry["positionHead"]["trainedRounds"] == list(range(1, entry["round"]))
    for arm in ("positionHead", "production"):
        for block in ("sprint", "feature", "pooled"):
            assert ab["walkForward"][arm][block]["n_rounds"] == ab["roundsCompared"]
    verdict = ab["verdict"]
    assert verdict["recommendation"] in {
        "position-head-better", "production-better", "inconclusive"
    }
    assert verdict["positionHeadMeanError"] is not None
    assert verdict["productionMeanError"] is not None


# --------------------------------------------------------------------------- #
# Walk-forward headline eval (forward_eval additive shape)
# --------------------------------------------------------------------------- #
def test_per_round_files_extend_existing_shape(data_dir):
    files = sorted((data_dir / "forward_eval").glob("round_*.json"))
    assert len(files) == config.COMPLETED_ROUNDS
    for path in files:
        rj = json.loads(path.read_text())
        # original keys intact (the website reads them)
        assert set(rj) >= {"round", "venueName", "sprint", "feature"}
        assert rj["sprint"]["n"] > 0 and rj["feature"]["n"] > 0
        # additive: per-market probability quality + last-race baseline
        for rt in ("sprint", "feature"):
            markets = rj["markets"][rt]
            for market in ("win", "podium"):
                assert markets[market]["brier"] is not None
                assert markets[market]["logLoss"] is not None
                assert 0.0 <= markets[market]["brier"] <= 1.0
            if rj["round"] == 1:
                assert rj["baselines"][rt] is None  # no prior race to copy
            else:
                assert rj["baselines"][rt]["n"] > 0


def test_season_summary_has_walk_forward_block(data_dir):
    season = json.loads((data_dir / "forward_eval" / "season.json").read_text())
    # original keys intact
    assert set(season) >= {
        "season", "roundsScored", "meanPositionError", "meanNdcgAt5",
        "winnerHitRate", "podiumHitRate",
    }
    assert season["roundsScored"] == config.COMPLETED_ROUNDS
    # additive headline block
    assert season["finishersOnly"] is True
    for rt in ("sprint", "feature"):
        block = season["walkForward"][rt]
        assert block["model"]["n_rounds"] == config.COMPLETED_ROUNDS
        metrics = block["model"]["metrics"]
        for key in ("mean_position_error", "winnerHit", "winBrier", "winLogLoss",
                    "podiumBrier", "podiumLogLoss"):
            assert key in metrics
            assert set(metrics[key]) >= {"mean", "median", "min", "max", "last", "trend", "n"}
        # baseline exists for rounds 2..N (round 1 has no prior race)
        assert block["baselines"]["lastRace"]["n_rounds"] == config.COMPLETED_ROUNDS - 1
    # season roll-up mean matches the walk-forward feature-race mean
    wf_mean = season["walkForward"]["feature"]["model"]["metrics"]["mean_position_error"]["mean"]
    assert season["meanPositionError"] == pytest.approx(wf_mean, abs=1e-3)


# --------------------------------------------------------------------------- #
# Promotion gate integration
# --------------------------------------------------------------------------- #
def test_promotion_status_with_candidate(data_dir):
    status = promotion_decision.build_status(data_dir)
    # original contract keys intact
    assert set(status) >= {
        "decision", "reason", "roundsCompared", "meanProduction",
        "meanCandidate", "relativeChange", "hasCandidate",
    }
    assert status["hasCandidate"] is True
    assert status["candidate"] == "position-head"
    assert status["candidateFlag"] == position_head.ENV_FLAG
    assert status["abVerdict"]["recommendation"] in {
        "position-head-better", "production-better", "inconclusive"
    }
    assert status["decision"] in {"promote", "hold", "demote"}


def test_promotion_status_without_candidate(tmp_path, data_dir):
    """No A/B artifact → the honest Phase-1 'hold for want of a candidate'."""
    fe_dir = tmp_path / "forward_eval"
    fe_dir.mkdir()
    for path in (data_dir / "forward_eval").glob("round_*.json"):
        (fe_dir / path.name).write_text(path.read_text())
    status = promotion_decision.build_status(tmp_path)
    assert status["hasCandidate"] is False
    assert status["candidate"] is None
    assert status["abVerdict"] is None
    assert status["decision"] == "hold"
