"""The unique-MotoGP-model behaviours: shared grid, sprint variance, spread markets."""
from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from motogp_predictions import config, model
from motogp_predictions.datasource import MotoGPDataSource


@pytest.fixture
def source():
    return MotoGPDataSource()


@pytest.fixture
def forecast(source):
    grid = source.qualifying(config.SEASON, config.COMPLETED_ROUNDS)
    return model.forecast_round(
        source, config.SEASON, config.COMPLETED_ROUNDS, n_samples=3000, known_grid=grid
    )


def test_each_race_is_a_full_permutation(forecast):
    codes = sorted(d["code"] for d in config.DRIVERS)
    for race in (forecast.sprint, forecast.feature):
        assert sorted(race.order) == codes
        assert sorted(race.grid) == codes
        assert len(set(race.grid)) == len(config.DRIVERS)  # no duplicate grid slots


def test_sprint_shares_the_grand_prix_grid(forecast):
    # MotoGP has no reverse grid: the Saturday Sprint starts from the SAME
    # qualifying order as Sunday's Grand Prix.
    assert forecast.sprint.grid == forecast.feature.grid


def test_sprint_runs_hotter_than_the_grand_prix(forecast):
    # The sprint is shorter and higher-variance → a hotter Plackett-Luce temperature.
    assert forecast.sprint.temperature > forecast.feature.temperature
    # Higher variance flattens the win market: the favourite is less concentrated.
    assert max(forecast.sprint.markets.p_win.values()) <= max(forecast.feature.markets.p_win.values())


def test_markets_are_normalised_and_non_degenerate(forecast):
    # The suite-wide anti-collapse contract for a ~29-rider field: the win market
    # is spread (many live contenders, no over-confident favourite, normalised)
    # rather than strictly all-positive (backmarker p_win legitimately rounds to 0).
    for race in (forecast.sprint, forecast.feature):
        pw = race.markets.p_win
        assert abs(sum(pw.values()) - 1.0) < 0.02, "win market not normalised"
        assert max(pw.values()) < 0.85, "degenerate over-confident favourite"
        assert sum(1 for p in pw.values() if p > 0) >= 8, "market collapsed onto too few riders"


def test_cumulative_markets_are_monotonic_and_finite(forecast):
    for race in (forecast.sprint, forecast.feature):
        m = race.markets
        for code in race.order:
            for v in (m.p_win[code], m.p_podium[code], m.p_top6[code], m.p_top10[code]):
                assert not math.isnan(v)
            assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


def test_forecast_shapes_and_ranges(forecast):
    for race in (forecast.sprint, forecast.feature):
        assert len(race.order) == len(config.DRIVERS)
        for code in race.order:
            assert 1 <= race.range_low[code] <= race.range_high[code] <= len(config.DRIVERS)
            assert 1.0 <= race.mean_finish[code] <= float(len(config.DRIVERS))


def test_post_quali_pole_leads_the_grand_prix_grid(source):
    # With the real grid known, the Grand Prix grid IS the qualifying order.
    rnd = config.COMPLETED_ROUNDS
    grid = source.qualifying(config.SEASON, rnd)
    fc = model.forecast_round(source, config.SEASON, rnd, n_samples=1500, known_grid=grid)
    assert fc.feature.grid[0] == grid[0]


def test_championship_scales_with_remaining_rounds(source):
    skill = model.estimate_skill(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    points = {d["code"]: 0.0 for d in config.DRIVERS}
    few = model.project_championship_motogp(points, skill, remaining_rounds=1, n_samples=800)
    many = model.project_championship_motogp(points, skill, remaining_rounds=6, n_samples=800)
    few_mean = {p.key: p.proj_mean for p in few}
    many_mean = {p.key: p.proj_mean for p in many}
    leader = many[0].key
    # More rounds to come → more projected points accumulated on average.
    assert many_mean[leader] > few_mean[leader]
    # Title probabilities are a proper distribution.
    assert abs(sum(p.p_title for p in many) - 1.0) < 1e-6
