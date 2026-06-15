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
