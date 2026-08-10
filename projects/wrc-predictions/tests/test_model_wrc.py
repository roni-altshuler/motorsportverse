"""The unique-WRC-model behaviours: one rally per round, the surface variable, and
spread (non-degenerate) markets over a large rally field."""
from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from motorsport_core import calibration

from wrc_predictions import config, model
from wrc_predictions.datasource import WrcDataSource


@pytest.fixture
def source():
    return WrcDataSource()


@pytest.fixture
def forecast(source):
    return model.forecast_round(source, config.SEASON, config.COMPLETED_ROUNDS, n_samples=3000)


def test_round_is_a_single_rally_no_grid_no_sprint(forecast):
    # A WRC round is ONE scored classification: it carries a `rally` and nothing
    # else — no sprint, no feature race, and no qualifying grid to condition on.
    assert hasattr(forecast, "rally")
    assert not hasattr(forecast, "sprint")
    assert not hasattr(forecast, "feature")
    assert not hasattr(forecast.rally, "grid")


def test_rally_is_a_full_permutation(forecast):
    codes = sorted(d["code"] for d in config.DRIVERS)
    assert sorted(forecast.rally.order) == codes


def test_surface_is_present_and_valid(forecast):
    # The surface is the defining rally variable and must be surfaced everywhere.
    assert forecast.surface in config.SURFACE_COLORS
    assert forecast.rally.surface == forecast.surface
    assert all(
        config.surface_for_round(r) in config.SURFACE_COLORS
        for r in range(1, config.TOTAL_ROUNDS + 1)
    )


def test_markets_are_normalised_and_non_degenerate(forecast):
    # The suite-wide anti-collapse contract over a large rally field: the win market
    # is normalised, has no over-confident favourite, and is spread across many
    # live crews (the ensemble normalises p_win to sum 1.0).
    pw = forecast.rally.markets.p_win
    assert abs(sum(pw.values()) - 1.0) < 0.02, "win market not normalised"
    assert max(pw.values()) < 0.85, "degenerate over-confident favourite"
    assert sum(1 for p in pw.values() if p > 0) >= 8, "market collapsed onto too few crews"


def test_cumulative_markets_are_monotonic_and_finite(forecast):
    m = forecast.rally.markets
    for code in forecast.rally.order:
        for v in (m.p_win[code], m.p_podium[code], m.p_top6[code], m.p_top10[code]):
            assert not math.isnan(v)
        assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


def test_forecast_shapes_and_ranges(forecast):
    r = forecast.rally
    assert len(r.order) == len(config.DRIVERS)
    for code in r.order:
        assert 1 <= r.range_low[code] <= r.range_high[code] <= len(config.DRIVERS)
        assert 1.0 <= r.mean_finish[code] <= float(len(config.DRIVERS))


def test_forecast_is_an_ensemble_not_the_bare_skill_model(source):
    # The production forecast ENSEMBLES the skill model with a championship-form
    # prior, so its win market differs from the raw skill-only Plackett-Luce market.
    rnd = config.COMPLETED_ROUNDS
    ensemble = model.forecast_round(source, config.SEASON, rnd, n_samples=1500).rally.markets.p_win
    pace = model.estimate_skill(source, config.SEASON, rnd)
    skill_only = calibration.plackett_luce_probabilities(pace, n_samples=1500).p_win
    assert ensemble != skill_only


def test_championship_scales_with_remaining_rounds(source):
    skill = model.estimate_skill(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    points = {d["code"]: 0.0 for d in config.DRIVERS}
    few = model.project_championship_wrc(points, skill, remaining_rounds=1, n_samples=800)
    many = model.project_championship_wrc(points, skill, remaining_rounds=6, n_samples=800)
    few_mean = {p.key: p.proj_mean for p in few}
    many_mean = {p.key: p.proj_mean for p in many}
    leader = many[0].key
    # More rounds to come → more projected points accumulated on average.
    assert many_mean[leader] > few_mean[leader]
    # Title probabilities are a proper distribution.
    assert abs(sum(p.p_title for p in many) - 1.0) < 1e-6
