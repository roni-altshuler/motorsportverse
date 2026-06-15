"""Tests for the reusable standings module."""

from motorsport_core import standings

# A simple top-3 points table.
POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10}


def test_driver_standings_accumulate_and_rank():
    results = [
        {"A": 1, "B": 2, "C": 3},
        {"A": 2, "B": 1, "C": 4},
    ]
    table = standings.compute_driver_standings(results, POINTS)
    keys = [r.key for r in table]
    # A: 25+18=43, B: 18+25=43 -> tie on points, A has 1 win, B has 1 win,
    # both 2 podiums; best_finish both 1 -> stable order A,B by insertion via sort.
    assert set(keys[:2]) == {"A", "B"}
    a = next(r for r in table if r.key == "A")
    assert a.points == 43
    assert a.wins == 1
    assert a.podiums == 2
    assert a.rounds == 2
    assert a.best_finish == 1


def test_tiebreak_by_wins():
    results = [
        {"A": 1, "B": 3},  # A 25, B 15
        {"A": 3, "B": 1},  # A 15, B 25  -> both 40
        {"A": 1, "B": 2},  # A 25 (win), B 18
    ]
    table = standings.compute_driver_standings(results, POINTS)
    # A has 2 wins, B has 1 win -> A ranks first even if points were equal.
    assert table[0].key == "A"
    assert table[0].wins == 2


def test_team_standings_sum_members():
    results = [{"A": 1, "B": 2, "C": 3, "D": 4}]
    team_of = {"A": "Red", "B": "Blue", "C": "Red", "D": "Blue"}
    table = standings.compute_team_standings(results, POINTS, team_of)
    red = next(r for r in table if r.key == "Red")
    blue = next(r for r in table if r.key == "Blue")
    assert red.points == 25 + 15  # A(1)+C(3)
    assert blue.points == 18 + 12  # B(2)+D(4)
    assert table[0].key == "Red"


def test_bonus_points_added():
    results = [{"A": 2, "B": 1}]
    table = standings.compute_driver_standings(results, POINTS, bonus={"A": 1.0})
    a = next(r for r in table if r.key == "A")
    assert a.points == 18 + 1.0  # P2 + pole bonus


def test_points_for_outside_table_is_zero():
    assert standings.points_for(50, POINTS) == 0.0


def test_merge_standings_combines_points_tables():
    # F2-style: sprint table + feature table merged.
    sprint_pts = {1: 10, 2: 8, 3: 6}
    feature_pts = {1: 25, 2: 18, 3: 15}
    sprint = standings.compute_driver_standings([{"A": 1, "B": 2}], sprint_pts)
    feature = standings.compute_driver_standings([{"A": 2, "B": 1}], feature_pts)
    merged = standings.merge_standings(sprint, feature)
    a = next(r for r in merged if r.key == "A")
    b = next(r for r in merged if r.key == "B")
    assert a.points == 10 + 18  # sprint win + feature P2
    assert b.points == 8 + 25  # sprint P2 + feature win
    assert a.rounds == 2 and b.rounds == 2
    assert b.wins == 1  # one feature win
    assert merged[0].key == "B"  # more points
