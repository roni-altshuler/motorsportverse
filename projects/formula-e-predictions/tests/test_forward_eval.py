"""Forward-eval unit tests: baselines, metric bundles, walk-forward blocks.

The end-to-end forward_eval tree is exercised by test_website_data_schema.py's
module fixture; these tests cover the pieces in isolation.
"""
from __future__ import annotations

from formula_e_predictions import config, forward_eval as fe

SEASON = config.SEASON


def test_grid_map_prefers_recorded_grid(real_source):
    grid = fe._grid_map(real_source, SEASON, 13)
    assert grid is not None and len(grid) >= 15
    # Shanghai II: Drugovich started on pole, Di Grassi P19 (and won).
    assert grid["DRU"] == 1
    assert grid["DIG"] == 19


def test_grid_map_none_without_real_data():
    from formula_e_predictions.datasource import FEDataSource
    from formula_e_predictions.sources.synthetic import SyntheticFESource

    source = FEDataSource(source=SyntheticFESource())
    assert fe._grid_map(source, SEASON, 1) is None


def test_round_metric_bundle_flattens_markets():
    r = {
        "race": {"n": 18, "mean_position_error": 4.5, "winner_hit": True, "podium_hits": 2},
        "markets": {"race": {"win": {"brier": 0.05, "logLoss": 0.2}}},
    }
    bundle = fe._round_metric_bundle(r)
    assert bundle["winnerHit"] == 1.0
    assert bundle["mean_position_error"] == 4.5
    assert bundle["winBrier"] == 0.05
    assert "n" not in bundle


def test_baseline_metric_bundle_none_when_absent():
    assert fe._baseline_metric_bundle({"baselines": {"lastRace": None}}, "lastRace") is None


def test_build_walk_forward_summary_shape():
    rounds = [
        {
            "race": {"n": 18, "mean_position_error": 5.0, "winner_hit": False, "podium_hits": 1},
            "markets": {"race": {}},
            "baselines": {
                "lastRace": None,
                "gridOrder": {"n": 18, "mean_position_error": 6.0, "winner_hit": True},
            },
        },
        {
            "race": {"n": 18, "mean_position_error": 4.0, "winner_hit": True, "podium_hits": 2},
            "markets": {"race": {}},
            "baselines": {
                "lastRace": {"n": 18, "mean_position_error": 5.5, "winner_hit": False},
                "gridOrder": {"n": 18, "mean_position_error": 5.0, "winner_hit": False},
            },
        },
    ]
    wf = fe.build_walk_forward_summary(rounds)
    block = wf["race"]
    assert block["model"]["n_rounds"] == 2
    assert block["model"]["metrics"]["mean_position_error"]["mean"] == 4.5
    assert block["baselines"]["lastRace"]["n_rounds"] == 1
    assert block["baselines"]["gridOrder"]["n_rounds"] == 2
    assert block["baselines"]["gridOrder"]["metrics"]["winnerHit"]["mean"] == 0.5


def test_market_scores_bundle(real_source):
    from formula_e_predictions import pipeline

    fc = pipeline.forecast_round(real_source, SEASON, 2)
    actual = fe._actuals(real_source, SEASON, 2)
    scores = fe._market_scores(fc.race, actual)
    assert set(scores) == {"win", "podium"}
    for m in scores.values():
        assert 0.0 <= m["brier"] <= 1.0
        assert m["logLoss"] >= 0.0
