"""Tests for the reusable Monte Carlo championship projection."""

from motorsport_core import championship

POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8}


def test_probabilities_sum_to_one_and_sorted():
    strengths = {"A": 90.0, "B": 90.4, "C": 90.8, "D": 91.5}
    current = {"A": 100, "B": 80, "C": 60, "D": 40}
    proj = championship.project_championship(
        current, strengths, remaining_rounds=5, points=POINTS, n_samples=2000
    )
    total = sum(p.p_title for p in proj)
    assert abs(total - 1.0) < 1e-6
    # sorted by descending title probability
    assert proj == sorted(proj, key=lambda p: -p.p_title)


def test_clear_leader_dominates():
    # A is both well ahead on points AND fastest -> should win the title most often.
    strengths = {"A": 89.0, "B": 91.0, "C": 91.5}
    current = {"A": 200, "B": 50, "C": 40}
    proj = championship.project_championship(
        current, strengths, remaining_rounds=2, points=POINTS, n_samples=1500
    )
    leader = proj[0]
    assert leader.key == "A"
    assert leader.p_title > 0.9


def test_zero_remaining_rounds_decides_on_current_points():
    strengths = {"A": 90.0, "B": 90.0}
    current = {"A": 120, "B": 119}
    proj = championship.project_championship(
        current, strengths, remaining_rounds=0, points=POINTS, n_samples=10
    )
    leader = next(p for p in proj if p.key == "A")
    assert leader.p_title == 1.0


def test_deterministic_with_seed():
    strengths = {"A": 90.0, "B": 90.5, "C": 91.0}
    current = {"A": 0, "B": 0, "C": 0}
    a = championship.project_championship(current, strengths, 3, POINTS, n_samples=500, seed=7)
    b = championship.project_championship(current, strengths, 3, POINTS, n_samples=500, seed=7)
    assert [p.p_title for p in a] == [p.p_title for p in b]


def test_races_per_round_scales_points():
    strengths = {"A": 90.0, "B": 90.5}
    current = {"A": 0, "B": 0}
    one = championship.project_championship(current, strengths, 5, POINTS, n_samples=400, races_per_round=1)
    two = championship.project_championship(current, strengths, 5, POINTS, n_samples=400, races_per_round=2)
    # twice the scored races -> roughly twice the projected mean points
    mean_one = sum(p.proj_mean for p in one)
    mean_two = sum(p.proj_mean for p in two)
    assert mean_two > mean_one * 1.5
