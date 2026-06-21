"""Tests for the championship Monte Carlo simulator."""
from __future__ import annotations

import numpy as np
import pytest

from championship_simulator import (
    DEFAULT_DNF_PROBABILITY,
    RACE_POINTS,
    SimulationInputs,
    simulate_championships,
)


def _make_inputs(
    n_remaining: int = 5,
    driver_skills: dict[str, float] | None = None,
    initial_points: dict[str, float] | None = None,
    teams: dict[str, str] | None = None,
) -> SimulationInputs:
    if driver_skills is None:
        driver_skills = {"A": 0.5, "B": 0.3, "C": 0.2}
    drivers = list(driver_skills.keys())
    initial_points = initial_points or {d: 0.0 for d in drivers}
    teams = teams or {drivers[0]: "RED", drivers[1]: "BLUE", drivers[2]: "RED"}
    teams_unique = list(dict.fromkeys(teams.values()))
    initial_constructor_points = {t: 0.0 for t in teams_unique}
    return SimulationInputs(
        drivers=drivers,
        driver_full_names={d: d for d in drivers},
        driver_teams=teams,
        driver_team_colors={d: "#888" for d in drivers},
        current_driver_points=initial_points,
        current_constructor_points=initial_constructor_points,
        win_probabilities=driver_skills,
        dnf_probabilities={d: DEFAULT_DNF_PROBABILITY for d in drivers},
        remaining_rounds=[
            {"round": 10 + i, "name": f"GP{i}", "sprint": False}
            for i in range(n_remaining)
        ],
    )


class TestSimulatorShape:
    def test_returns_both_forecasts(self):
        out = simulate_championships(_make_inputs(), n_samples=200)
        assert "wdcForecast" in out
        assert "wccForecast" in out
        assert len(out["wdcForecast"]) == 3
        assert len(out["wccForecast"]) == 2  # RED and BLUE

    def test_wdc_probabilities_sum_to_one(self):
        out = simulate_championships(_make_inputs(), n_samples=500)
        s = sum(r["championshipWinProbability"] for r in out["wdcForecast"])
        assert s == pytest.approx(1.0, abs=1e-6)

    def test_wcc_probabilities_sum_to_one(self):
        out = simulate_championships(_make_inputs(), n_samples=500)
        s = sum(r["championshipWinProbability"] for r in out["wccForecast"])
        assert s == pytest.approx(1.0, abs=1e-6)

    def test_forecast_sorted_by_probability(self):
        out = simulate_championships(_make_inputs(), n_samples=500)
        probs = [r["championshipWinProbability"] for r in out["wdcForecast"]]
        assert probs == sorted(probs, reverse=True)


class TestSimulatorBehaviour:
    def test_dominant_skill_leads_in_probability(self):
        # A heavily skewed skill vector should produce a clear favourite.
        inputs = _make_inputs(driver_skills={"A": 0.9, "B": 0.05, "C": 0.05})
        out = simulate_championships(inputs, n_samples=1000)
        winner = out["wdcForecast"][0]
        assert winner["driver"] == "A"
        assert winner["championshipWinProbability"] > 0.5

    def test_large_points_lead_holds_up(self):
        # If A starts with a 200-point head start over equal skill peers,
        # A should still win the championship majority of the time.
        inputs = _make_inputs(
            driver_skills={"A": 0.33, "B": 0.33, "C": 0.34},
            initial_points={"A": 200.0, "B": 0.0, "C": 0.0},
        )
        out = simulate_championships(inputs, n_samples=1000)
        winner = out["wdcForecast"][0]
        assert winner["driver"] == "A"
        assert winner["championshipWinProbability"] > 0.95

    def test_no_remaining_rounds_locks_current_leader(self):
        # When there are 0 races left, championship is decided by
        # current points. We confirm by passing zero remaining rounds.
        inputs = _make_inputs(
            n_remaining=0,
            initial_points={"A": 100.0, "B": 90.0, "C": 80.0},
        )
        out = simulate_championships(inputs, n_samples=200)
        assert out["wdcForecast"][0]["driver"] == "A"
        assert out["wdcForecast"][0]["championshipWinProbability"] == 1.0

    def test_expected_points_consistent_with_starting_points(self):
        # Expected final points must be >= starting points (only a
        # negative-points fastest-lap-from-pit-lane could ever shrink
        # them, and F1 doesn't do that).
        inputs = _make_inputs(
            initial_points={"A": 50.0, "B": 30.0, "C": 10.0},
        )
        out = simulate_championships(inputs, n_samples=300)
        starts = {"A": 50.0, "B": 30.0, "C": 10.0}
        for row in out["wdcForecast"]:
            assert row["expectedFinalPoints"] >= starts[row["driver"]]


class TestRacePoints:
    def test_race_points_top_3_match_f1_rules(self):
        assert RACE_POINTS[0] == 25
        assert RACE_POINTS[1] == 18
        assert RACE_POINTS[2] == 15

    def test_dnf_probability_default_in_reasonable_range(self):
        # Sanity: too high → noisy, too low → unrealistic.
        assert 0.03 <= DEFAULT_DNF_PROBABILITY <= 0.15


class TestDeterminism:
    def test_same_seed_same_output(self):
        inputs = _make_inputs()
        a = simulate_championships(inputs, n_samples=200, seed=1)
        b = simulate_championships(inputs, n_samples=200, seed=1)
        a_probs = [r["championshipWinProbability"] for r in a["wdcForecast"]]
        b_probs = [r["championshipWinProbability"] for r in b["wdcForecast"]]
        np.testing.assert_array_equal(a_probs, b_probs)
