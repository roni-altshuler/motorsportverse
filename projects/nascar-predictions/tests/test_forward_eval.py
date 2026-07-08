"""Forward-eval unit tests: baselines, metric bundles, walk-forward blocks.

The end-to-end forward_eval tree is exercised by test_website_data_schema.py's
module fixture; these tests cover the pieces in isolation.
"""
from __future__ import annotations

from nascar_predictions import config, forward_eval as fe

SEASON = config.SEASON


def test_grid_map_prefers_recorded_grid(real_source):
    grid = fe._grid_map(real_source, SEASON, 8)  # Bristol
    assert grid is not None and len(grid) >= 30
    assert grid["RYBLANEY"] == 1  # Blaney started on pole (verified feed)


def test_grid_map_none_without_real_data():
    from nascar_predictions.datasource import NascarDataSource
    from nascar_predictions.sources.synthetic import SyntheticNascarSource

    source = NascarDataSource(source=SyntheticNascarSource())
    # Synthetic results DO carry a grid (grid = position), so this exercises
    # the real-data preference: rows exist only via race_rows, which synthetic
    # doesn't implement → falls to qualifying → None.
    assert fe._grid_map(source, SEASON, 1) is None


def test_round_metric_bundle_flattens_markets():
    r = {
        "race": {"n": 38, "mean_position_error": 8.5, "winner_hit": True, "podium_hits": 2},
        "markets": {"race": {"win": {"brier": 0.03, "logLoss": 0.12}}},
    }
    bundle = fe._round_metric_bundle(r)
    assert bundle["winnerHit"] == 1.0
    assert bundle["mean_position_error"] == 8.5
    assert bundle["winBrier"] == 0.03
    assert "n" not in bundle


def test_baseline_metric_bundle_none_when_absent():
    assert fe._baseline_metric_bundle({"baselines": {"lastRace": None}}, "lastRace") is None


def test_build_walk_forward_summary_includes_post_quali_arm():
    rounds = [
        {
            "race": {"n": 38, "mean_position_error": 9.0, "winner_hit": False, "podium_hits": 1},
            "racePostQuali": {"n": 38, "mean_position_error": 8.5, "winner_hit": True},
            "markets": {"race": {}},
            "baselines": {
                "lastRace": None,
                "gridOrder": {"n": 38, "mean_position_error": 9.5, "winner_hit": True},
            },
        },
        {
            "race": {"n": 38, "mean_position_error": 10.0, "winner_hit": True, "podium_hits": 2},
            "racePostQuali": None,
            "markets": {"race": {}},
            "baselines": {
                "lastRace": {"n": 38, "mean_position_error": 10.5, "winner_hit": False},
                "gridOrder": None,
            },
        },
    ]
    wf = fe.build_walk_forward_summary(rounds)
    block = wf["race"]
    assert block["model"]["n_rounds"] == 2
    assert block["model"]["metrics"]["mean_position_error"]["mean"] == 9.5
    assert block["modelPostQuali"]["n_rounds"] == 1
    assert block["modelPostQuali"]["metrics"]["mean_position_error"]["mean"] == 8.5
    assert block["baselines"]["gridOrder"]["n_rounds"] == 1
    assert block["baselines"]["lastRace"]["n_rounds"] == 1


def test_market_scores_bundle(real_source):
    from nascar_predictions import pipeline

    fc = pipeline.forecast_round(real_source, SEASON, 2)
    actual = fe._actuals(real_source, SEASON, 2)
    scores = fe._market_scores(fc.race, actual)
    assert set(scores) == {"win", "podium"}
    for m in scores.values():
        assert 0.0 <= m["brier"] <= 1.0
        assert m["logLoss"] >= 0.0


def test_season_summary_flags_full_field_scoring():
    s = fe._season_summary(SEASON, [])
    assert s["finishersOnly"] is False
    assert s["roundsScored"] == 0
