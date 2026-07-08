"""Position head: gate, leakage-safe frames, re-ranking, A/B backtest."""
from __future__ import annotations

from nascar_predictions import config, model, position_head as ph

SEASON = config.SEASON


def test_gate_defaults_off(monkeypatch):
    monkeypatch.delenv(ph.ENV_FLAG, raising=False)
    assert ph.head_enabled() is False
    monkeypatch.setenv(ph.ENV_FLAG, "1")
    assert ph.head_enabled() is True
    assert ph.head_enabled(override=False) is False
    assert ph.head_enabled(override=True) is True


def test_extract_features_shape(real_source):
    fc = model.forecast_round(real_source, SEASON, 8, use_position_head=False)
    feats = ph.extract_race_features(fc.race, track_type=fc.track_type)
    assert set(feats) == set(fc.race.score)
    row = next(iter(feats.values()))
    assert set(row) == set(ph.FEATURE_NAMES)
    assert len(ph.MONOTONIC_CONSTRAINTS) == len(ph.FEATURE_NAMES)
    # Bristol is a short track: the one-hots must say so.
    assert all(f["isShort"] == 1.0 and f["isRoad"] == 0.0 for f in feats.values())


def test_training_frame_is_prior_only(truncated_source):
    forecasts, actuals = ph._prior_replays(truncated_source, SEASON, 4)
    assert set(forecasts) == {1, 2, 3}
    X, y, used = ph.build_training_frame(forecasts, actuals, 4)
    assert used == [1, 2, 3]
    assert X.shape[0] == len(y) > 90  # ~38 rows per Cup round
    # A map containing the target round itself is filtered out, never trained
    # on (the assert_prior_only boundary then blesses the filtered map).
    bad = dict(forecasts)
    bad[4] = forecasts[3]
    bad_actuals = dict(actuals)
    bad_actuals[4] = actuals[3]
    X2, y2, used2 = ph.build_training_frame(bad, bad_actuals, 4)
    assert used2 == [1, 2, 3]
    assert X2.shape == X.shape


def test_train_for_round_degrades_gracefully(truncated_source):
    head = ph.train_for_round(truncated_source, SEASON, 2, min_prior_rounds=3)
    assert head is None  # only one prior round


def test_maybe_rerank_records_metadata(truncated_source):
    fc = model.forecast_round(truncated_source, SEASON, 5, use_position_head=False)
    out = ph.maybe_rerank_round(truncated_source, SEASON, 5, fc, n_samples=800)
    assert out.position_head is not None
    assert out.position_head["applied"] is True
    assert out.position_head["trainedRounds"] == [1, 2, 3, 4]
    # The re-ranked race keeps the same grid and hazard (only ordering moves).
    assert out.race.grid == fc.race.grid
    assert out.race.p_dnf == fc.race.p_dnf


def test_rerank_stays_correlated_with_pace(truncated_source):
    """A healthy head re-ranks around the pace signal — never inverts it."""
    fc = model.forecast_round(truncated_source, SEASON, 6, use_position_head=False)
    head = ph.train_for_round(truncated_source, SEASON, 6, min_prior_rounds=3)
    assert head is not None
    feats = ph.extract_race_features(fc.race, track_type=fc.track_type)
    pred = head.predict_positions(feats)
    sanity = ph.monotonic_sanity(pred, feats)
    assert sanity is not None and sanity > 0.5


def test_run_backtest_shape(truncated_source):
    result = ph.run_backtest(truncated_source, SEASON, min_prior_rounds=3)
    assert result["roundsScored"] == 6
    assert result["roundsCompared"] == 3  # rounds 4-6 have >= 3 priors
    verdict = result["verdict"]
    assert verdict["recommendation"] in (
        "position-head-better", "production-better", "inconclusive",
    )
    assert result["walkForward"]["production"]["race"]["n_rounds"] == 3
