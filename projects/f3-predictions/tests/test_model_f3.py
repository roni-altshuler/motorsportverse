"""The unique-F3-model behaviours: sprint vs feature, reverse grid, rookies."""

import pytest

from f3_predictions import config, model
from f3_predictions.datasource import F3DataSource


@pytest.fixture
def source():
    return F3DataSource()


@pytest.fixture
def forecast(source):
    return model.forecast_round(source, config.SEASON, config.COMPLETED_ROUNDS + 1, n_samples=3000)


def test_sprint_and_feature_are_different_races(forecast):
    # Regression against the original single-order pipeline: the two heads must
    # produce genuinely different forecasts.
    assert forecast.sprint.order != forecast.feature.order
    assert forecast.sprint.grid != forecast.feature.grid


def test_sprint_grid_is_reversed_top_n_of_feature_merit(forecast):
    n = config.REVERSE_GRID_SIZE
    merit = forecast.feature.grid
    assert forecast.sprint.grid[:n] == merit[:n][::-1]
    # P(N+1) onward is unchanged by the reverse.
    assert forecast.sprint.grid[n:] == merit[n:]


def test_reverse_grid_flattens_the_sprint(forecast):
    # The fastest driver starts the sprint near the back, so the sprint win is
    # less concentrated than the feature win — the high-variance reverse-grid effect.
    top_feature = max(forecast.feature.markets.p_win.values())
    top_sprint = max(forecast.sprint.markets.p_win.values())
    assert top_sprint < top_feature


def test_feature_pole_is_the_fastest_driver(source, forecast):
    pace = model.estimate_skill(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    fastest = min(pace, key=lambda c: pace[c])
    assert forecast.feature.grid[0] == fastest


def test_rookie_with_no_history_gets_a_pooled_estimate(source):
    # Every driver — including a sparse-history one — gets a finite, sane pace
    # (Elo pools rookies to the team mean rather than producing garbage/field-mean only).
    pace = model.estimate_skill(source, config.SEASON, current_round=2)
    assert len(pace) == len(config.DRIVERS)
    assert all(80.0 < v < 100.0 for v in pace.values())
    flags = model.rookie_flags(source, config.SEASON, current_round=2)
    assert set(flags) == {d["code"] for d in config.DRIVERS}


def test_forecast_shapes_and_ranges(forecast):
    for race in (forecast.sprint, forecast.feature):
        assert len(race.order) == len(config.DRIVERS)
        assert sorted(race.order) == sorted(d["code"] for d in config.DRIVERS)
        for code in race.order:
            assert 1 <= race.range_low[code] <= race.range_high[code] <= len(config.DRIVERS)
            assert 1.0 <= race.mean_finish[code] <= float(len(config.DRIVERS))


def test_championship_scales_with_remaining_rounds(source):
    skill = model.estimate_skill(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    points = {d["code"]: 0.0 for d in config.DRIVERS}
    few = model.project_championship_f3(points, skill, remaining_rounds=1, n_samples=800)
    many = model.project_championship_f3(points, skill, remaining_rounds=5, n_samples=800)
    # More rounds to come → more projected points accumulated on average.
    few_mean = {p.key: p.proj_mean for p in few}
    many_mean = {p.key: p.proj_mean for p in many}
    leader = many[0].key
    assert many_mean[leader] > few_mean[leader]
