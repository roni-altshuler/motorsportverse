"""Tests for the sport-agnostic forward-eval metrics."""

import math

from motorsport_core import eval as mev


def test_spearman_perfect_and_inverse():
    pred = [1, 2, 3, 4, 5]
    assert math.isclose(mev.spearman_correlation(pred, pred), 1.0)
    assert math.isclose(mev.spearman_correlation(pred, list(reversed(pred))), -1.0)


def test_spearman_too_few():
    assert mev.spearman_correlation([1, 2], [2, 1]) is None


def test_ndcg_perfect():
    order = {f"D{i}": i for i in range(1, 11)}
    assert math.isclose(mev.ndcg_at_k(order, order, 5), 1.0)


def test_within_n_and_error():
    pred = {"A": 1, "B": 2, "C": 3}
    act = {"A": 1, "B": 4, "C": 3}
    assert mev.within_n(pred, act, 0) == 2  # A and C exact
    assert mev.within_n(pred, act, 2) == 3
    assert math.isclose(mev.mean_position_error(pred, act), (0 + 2 + 0) / 3)


def test_score_round_bundle():
    pred = {"A": 1, "B": 2, "C": 3, "D": 4}
    act = {"A": 1, "B": 3, "C": 2, "D": 4}
    s = mev.score_round(pred, act)
    assert s["n"] == 4
    assert s["winner_hit"] is True
    assert s["exact_matches"] == 2  # A, D
    assert s["podium_hits"] == 3
    assert s["ndcg_at_5"] is None  # only 4 common competitors, need >= 5


def test_average_ranks_ties():
    # two competitors tied on value 5 -> share average rank
    ranks = mev.average_ranks([5, 5, 1])
    assert ranks[2] == 1.0
    assert ranks[0] == ranks[1] == 2.5


def test_brier_score_perfect_and_worst():
    probs = {"A": 1.0, "B": 0.0}
    outcomes = {"A": 1, "B": 0}
    assert math.isclose(mev.brier_score(probs, outcomes), 0.0)
    worst = {"A": 0.0, "B": 1.0}
    assert math.isclose(mev.brier_score(worst, outcomes), 1.0)


def test_brier_score_partial_and_bool_outcomes():
    probs = {"A": 0.5, "B": 0.5}
    outcomes = {"A": True, "B": False}
    assert math.isclose(mev.brier_score(probs, outcomes), 0.25)


def test_brier_score_no_overlap():
    assert mev.brier_score({"A": 0.5}, {"B": 1}) is None


def test_log_loss_finite_on_confident_miss():
    # p=0 with outcome=1 would be -inf without clipping; eps keeps it finite.
    ll = mev.log_loss({"A": 0.0}, {"A": 1})
    assert ll is not None and math.isfinite(ll) and ll > 0


def test_log_loss_perfect_near_zero():
    ll = mev.log_loss({"A": 1.0, "B": 0.0}, {"A": 1, "B": 0})
    assert ll is not None and ll < 1e-6


def test_walk_forward_summary_basic():
    rounds = [
        {"mean_position_error": 3.0, "winner_hit": True, "spearman_correlation": 0.5},
        {"mean_position_error": 2.0, "winner_hit": False, "spearman_correlation": 0.7},
        {"mean_position_error": 1.0, "winner_hit": True, "spearman_correlation": 0.9},
    ]
    summ = mev.walk_forward_summary(rounds)
    assert summ["n_rounds"] == 3
    mpe = summ["metrics"]["mean_position_error"]
    assert math.isclose(mpe["mean"], 2.0)
    assert math.isclose(mpe["median"], 2.0)
    assert mpe["last"] == 1.0
    assert mpe["trend"] < 0  # improving (error dropping)
    # bool metrics are NOT aggregated
    assert "winner_hit" not in summ["metrics"]


def test_walk_forward_summary_skips_none_per_metric():
    rounds = [
        {"ndcg_at_5": None},
        {"ndcg_at_5": 0.8},
        {"ndcg_at_5": 0.6},
    ]
    summ = mev.walk_forward_summary(rounds)
    ndcg = summ["metrics"]["ndcg_at_5"]
    assert ndcg["n"] == 2
    assert math.isclose(ndcg["mean"], 0.7)


def test_walk_forward_summary_empty():
    assert mev.walk_forward_summary([]) == {"n_rounds": 0, "metrics": {}}
