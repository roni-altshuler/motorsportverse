"""Tests for the sport-agnostic key-factor generator."""

import math

from motorsport_core import explain


def _simple_field():
    # Three competitors. Feature "quali" is lower-is-better (a lap time);
    # "form" is higher-is-better (recent points).
    importances = {"quali": 0.7, "form": 0.3}
    groups = {"quali": "Qualifying pace", "form": "Recent form"}
    values = {
        "FAST": {"quali": 78.0, "form": 90.0},   # fast lap (low), strong form
        "MID": {"quali": 80.0, "form": 50.0},     # average
        "SLOW": {"quali": 82.0, "form": 10.0},    # slow lap (high), weak form
    }
    return importances, values, groups


def test_advantage_and_risk_directions():
    importances, values, groups = _simple_field()
    out = explain.explain_scores(
        importances, values, groups,
        lower_is_better={"quali"}, top_k=4,
    )
    # Fast driver: low quali time is an advantage.
    fast = {f["factor"]: f for f in out["FAST"]}
    assert fast["Qualifying pace"]["direction"] == "advantage"
    assert fast["Recent form"]["direction"] == "advantage"
    # Slow driver: high quali time is a risk (lower_is_better).
    slow = {f["factor"]: f for f in out["SLOW"]}
    assert slow["Qualifying pace"]["direction"] == "risk"
    assert slow["Recent form"]["direction"] == "risk"


def test_weights_normalized_zero_to_one():
    importances, values, groups = _simple_field()
    out = explain.explain_scores(importances, values, groups, lower_is_better={"quali"})
    for factors in out.values():
        for f in factors:
            assert 0.0 <= f["weight"] <= 1.0
        # any competitor with a non-zero contribution normalizes its top to 1.0
        top = max((f["weight"] for f in factors), default=0.0)
        if top > 0:
            assert math.isclose(top, 1.0)
    # FAST is off-average on both features -> must reach 1.0
    assert math.isclose(max(f["weight"] for f in out["FAST"]), 1.0)


def test_top_k_limit():
    importances = {f"f{i}": 1.0 for i in range(6)}
    groups = {f"f{i}": f"Group {i}" for i in range(6)}
    values = {
        "A": {f"f{i}": float(i) for i in range(6)},
        "B": {f"f{i}": float(i + 1) for i in range(6)},
        "C": {f"f{i}": float(2 * i) for i in range(6)},
    }
    out = explain.explain_scores(importances, values, groups, top_k=3)
    for factors in out.values():
        assert len(factors) <= 3


def test_neutral_when_at_field_average():
    importances = {"x": 1.0}
    groups = {"x": "Team performance"}
    values = {"A": {"x": 0.0}, "B": {"x": 10.0}, "C": {"x": 5.0}}
    out = explain.explain_scores(importances, values, groups, neutral_threshold=0.25)
    # C is exactly the mean -> z=0 -> neutral.
    c_factor = out["C"][0]
    assert c_factor["direction"] == "neutral"
    assert c_factor["weight"] == 0.0


def test_flat_feature_contributes_nothing():
    # A feature with no spread yields z=0 for everyone.
    importances = {"flat": 5.0, "real": 1.0}
    groups = {"flat": "Weather", "real": "Experience"}
    values = {
        "A": {"flat": 3.0, "real": 1.0},
        "B": {"flat": 3.0, "real": 5.0},
        "C": {"flat": 3.0, "real": 9.0},
    }
    out = explain.explain_scores(importances, values, groups)
    for factors in out.values():
        labels = {f["factor"] for f in factors if f["weight"] > 0}
        assert "Weather" not in labels  # flat -> zero contribution


def test_missing_and_nan_values_treated_as_average():
    importances = {"x": 1.0}
    groups = {"x": "Circuit history"}
    values = {
        "A": {"x": 1.0},
        "B": {"x": 5.0},
        "C": {},  # missing -> average -> neutral, no crash
        "D": {"x": float("nan")},
    }
    out = explain.explain_scores(importances, values, groups)
    assert out["C"][0]["direction"] == "neutral"
    assert out["D"][0]["direction"] == "neutral"


def test_zero_importance_feature_ignored():
    importances = {"used": 1.0, "unused": 0.0}
    groups = {"used": "Qualifying pace", "unused": "Reliability risk"}
    values = {
        "A": {"used": 1.0, "unused": 100.0},
        "B": {"used": 2.0, "unused": 0.0},
        "C": {"used": 3.0, "unused": 50.0},
    }
    out = explain.explain_scores(importances, values, groups)
    for factors in out.values():
        assert all(f["factor"] != "Reliability risk" for f in factors)


def test_deterministic():
    importances, values, groups = _simple_field()
    a = explain.explain_scores(importances, values, groups, lower_is_better={"quali"})
    b = explain.explain_scores(importances, values, groups, lower_is_better={"quali"})
    assert a == b


def test_empty_field_returns_empty():
    assert explain.explain_scores({"x": 1.0}, {}, {"x": "Weather"}) == {}


def test_ungrouped_features_ignored():
    importances = {"x": 1.0, "y": 1.0}
    groups = {"x": "Qualifying pace"}  # y ungrouped
    values = {"A": {"x": 1.0, "y": 9.0}, "B": {"x": 2.0, "y": 1.0}, "C": {"x": 3.0, "y": 5.0}}
    out = explain.explain_scores(importances, values, groups)
    for factors in out.values():
        assert all(f["factor"] == "Qualifying pace" for f in factors)
