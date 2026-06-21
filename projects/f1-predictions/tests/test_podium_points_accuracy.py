"""Tests for the podium-weighted classification accuracy metric."""
from advanced_models import podium_points_accuracy


def _perfect():
    order = {d: i + 1 for i, d in enumerate("ABCDEFGHIJ")}
    return order, dict(order)


def test_perfect_prediction_is_100():
    pred, act = _perfect()
    m = podium_points_accuracy(pred, act)
    assert m["podium_accuracy_pct"] == 100.0
    assert m["points_accuracy_pct"] == 100.0
    assert m["accuracy_pct"] == 100.0


def test_set_membership_ignores_order_within_group():
    # Right three podium drivers, but P2/P3 swapped — still full podium credit.
    pred = {"A": 1, "B": 2, "C": 3, "D": 4}
    act = {"A": 1, "C": 2, "B": 3, "D": 4}
    m = podium_points_accuracy(pred, act)
    assert m["podium_hits"] == 3
    assert m["podium_accuracy_pct"] == 100.0


def test_blend_is_podium_weighted_60_40():
    # 2/3 podium drivers, 6/10 points drivers -> 0.6*66.7 + 0.4*60 = 64.0
    pred = {"A": 1, "VER": 2, "B": 3, "X1": 4, "X2": 5, "C": 6, "D": 7,
            "X3": 8, "E": 9, "F": 10}
    act = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "G": 6, "F": 7,
           "H": 8, "I": 9, "J": 10}
    m = podium_points_accuracy(pred, act)
    assert m["podium_hits"] == 2 and m["podium_total"] == 3
    assert m["podium_accuracy_pct"] == 66.7
    assert m["points_hits"] == 6 and m["points_total"] == 10
    assert m["points_accuracy_pct"] == 60.0
    assert m["accuracy_pct"] == 64.0


def test_winner_called_lifts_podium_even_with_misses():
    # Only the winner is in the right group; rest are wrong -> 1/3 podium.
    pred = {"A": 1, "Z1": 2, "Z2": 3, "Z3": 4}
    act = {"A": 1, "B": 2, "C": 3, "Z1": 4}
    m = podium_points_accuracy(pred, act)
    assert m["podium_hits"] == 1
    assert m["podium_accuracy_pct"] == 33.3


def test_empty_inputs_return_none():
    assert podium_points_accuracy({}, {"A": 1}) is None
    assert podium_points_accuracy({"A": 1}, {}) is None
