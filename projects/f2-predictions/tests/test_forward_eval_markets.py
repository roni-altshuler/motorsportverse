"""Win/podium scoring includes known retirements without inventing absent results."""
from types import SimpleNamespace

import pytest

from f2_predictions import forward_eval
from motorsport_data.schema import Result


def forecast():
    return SimpleNamespace(markets=SimpleNamespace(
        p_win={"WIN": 0.1, "DNF": 0.8, "ABSENT": 0.1},
        p_podium={"WIN": 0.7, "DNF": 0.9, "ABSENT": 0.8},
    ))


def test_retirement_counts_as_negative_win_and_podium_outcome():
    scores = forward_eval._market_scores(forecast(), {"WIN": 1, "DNF": None})
    assert scores["win"]["n"] == 2
    assert scores["podium"]["n"] == 2
    assert scores["win"]["brier"] == pytest.approx((0.9 ** 2 + 0.8 ** 2) / 2)
    assert scores["podium"]["brier"] == pytest.approx((0.3 ** 2 + 0.9 ** 2) / 2)


def test_incomplete_result_without_a_winner_is_not_scored():
    assert forward_eval._market_scores(forecast(), {"DNF": None}) == {}
    assert forward_eval._market_scores(forecast(), {"WIN": 2}) == {}
    assert forward_eval._market_scores(forecast(), {}) == {}


def test_reported_retirements_remain_separate_from_rank_metrics():
    rows = [Result(competitor="WIN", position=1, status="Finished"),
            Result(competitor="DNF", position=None, status="Accident")]
    source = SimpleNamespace(race_results_for_round=lambda *_: {"sprint": rows, "feature": rows})
    assert forward_eval._reported_actuals(source, 2026, 1)["feature"] == {"WIN": 1, "DNF": None}
    assert forward_eval._actuals(source, 2026, 1)["feature"] == {"WIN": 1}


def test_season_replay_passes_all_reported_entrants_to_probability_scoring(monkeypatch):
    rows = [Result(competitor="WIN", position=1), Result(competitor="DNF", position=None)]
    source = SimpleNamespace(race_results_for_round=lambda *_: {"sprint": rows, "feature": rows})
    race = forecast()
    race.order = ["DNF", "WIN", "ABSENT"]
    monkeypatch.setattr(forward_eval, "F2DataSource", lambda: source)
    monkeypatch.setattr(forward_eval.config, "COMPLETED_ROUNDS", 1)
    monkeypatch.setattr(forward_eval.pipeline, "forecast_round", lambda *_: SimpleNamespace(
        sprint=race, feature=race, venue_name="Test circuit"))
    result = forward_eval.evaluate_season(2026)[0]
    assert result["feature"]["n"] == 1
    assert result["markets"]["feature"]["win"]["n"] == 2
