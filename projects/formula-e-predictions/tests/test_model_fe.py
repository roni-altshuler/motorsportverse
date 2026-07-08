"""FE model tests: skill blend, era windowing, race head, championship MC."""
from __future__ import annotations

import pytest

from formula_e_predictions import config, model
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.synthetic import SyntheticFESource

SEASON = config.SEASON


@pytest.fixture()
def synthetic_source():
    return FEDataSource(source=SyntheticFESource())


# --------------------------------------------------------------------------- #
# Era helpers
# --------------------------------------------------------------------------- #
def test_fe_era_boundaries():
    assert model.fe_era_index(2015) == 0          # Gen1
    assert model.fe_era_index(2019) == 1          # Gen2
    assert model.fe_era_index(2023) == 2          # Gen3
    assert model.fe_era_index(2026) == 3          # Gen3 Evo (open era)
    assert model.fe_era_distance(2023, 2026) == 1
    assert model.fe_era_distance(2015, 2026) == 3
    assert model.fe_era_distance(2026, 2026) == 0


def test_elo_seed_seasons_window():
    seasons = model.elo_seed_seasons(2026, list(range(2015, 2026)))
    # Gen2 onward (config.ELO_FIRST_SEASON=2019); Gen1 is hard-cut.
    assert seasons == list(range(2019, 2026))
    # Seasons at/after the target year never leak in.
    assert all(s < 2027 for s in model.elo_seed_seasons(2027, list(range(2015, 2030))))


# --------------------------------------------------------------------------- #
# Skill estimation
# --------------------------------------------------------------------------- #
def test_skill_flat_at_round1_without_history(synthetic_source):
    """Pure synthetic mode has no prior seasons and no prior rounds at round 1."""
    pace = model.estimate_skill(synthetic_source, SEASON, 1)
    assert set(pace) == {d["code"] for d in config.DRIVERS}
    assert all(p == config.PACE_BASE for p in pace.values())


def test_skill_differentiates_with_history(synthetic_source):
    pace = model.estimate_skill(synthetic_source, SEASON, 4)
    values = list(pace.values())
    assert max(values) - min(values) > 0.1
    # The synthetic truth's fastest driver should rank near the top.
    order = sorted(pace, key=pace.get)
    truth_best = min(config._TRUTH_PACE, key=config._TRUTH_PACE.get)
    assert order.index(truth_best) < 5


def test_skill_uses_prior_seasons_at_round1(real_source):
    """With the committed 2019-2025 snapshots the Elo seed differentiates the
    field even before the season's first race."""
    pace = model.estimate_skill(real_source, SEASON, 1)
    values = list(pace.values())
    assert max(values) - min(values) > 0.05


def test_rookie_flags_veteran_grid(real_source):
    flags = model.rookie_flags(real_source, SEASON, 5)
    # FE's grid is veteran-heavy: nearly everyone has 3+ career races.
    assert sum(flags.values()) <= 3


# --------------------------------------------------------------------------- #
# Race head
# --------------------------------------------------------------------------- #
def test_forecast_round_shapes(real_source):
    fc = model.forecast_round(real_source, SEASON, 3)
    race = fc.race
    n = len(race.score)
    assert n == 20
    assert sorted(race.order) == sorted(race.grid)
    assert set(race.mean_finish) == set(race.score)
    assert fc.venue_kind in ("street", "circuit")
    assert abs(sum(race.markets.p_win.values()) - 1.0) < 0.05
    for c in race.score:
        assert race.range_low[c] <= race.range_high[c]
    # Production path: the position head is OFF by default.
    assert fc.position_head is None


def test_forecast_round_venue_kind_matches_calendar(real_source):
    assert model.forecast_round(real_source, SEASON, 2).venue_kind == "circuit"   # Mexico City
    assert model.forecast_round(real_source, SEASON, 9).venue_kind == "street"    # Monaco


def test_known_grid_conditions_forecast(real_source):
    """Post-quali: the real grid becomes the forecast grid and pole gains
    a track-position edge over the same driver starting last."""
    pace = model.estimate_skill(real_source, SEASON, 14)
    merit = sorted(pace, key=pace.get)
    reversed_grid = merit[::-1]
    fc = model.forecast_round(real_source, SEASON, 14, known_grid=reversed_grid)
    assert fc.race.grid == reversed_grid
    # The pace-fastest driver now starts last; their win probability must be
    # lower than in the merit-grid forecast.
    fc_merit = model.forecast_round(real_source, SEASON, 14)
    best = merit[0]
    assert fc.race.markets.p_win[best] < fc_merit.race.markets.p_win[best]


def test_complete_grid_handles_partial_and_junk():
    merit = ["A", "B", "C", "D"]
    grid = model._complete_grid(["C", "X", "A", "C"], merit)
    assert grid == ["C", "A", "B", "D"]


# --------------------------------------------------------------------------- #
# Championship MC
# --------------------------------------------------------------------------- #
def test_project_championship_no_remaining_rounds():
    points = {"AAA": 100.0, "BBB": 80.0}
    skill = {"AAA": 90.0, "BBB": 89.0}
    proj = model.project_championship_fe(points, skill, remaining_rounds=0, n_samples=200)
    assert proj[0].key == "AAA" and proj[0].p_title == 1.0
    assert proj[0].proj_mean == 100.0


def test_project_championship_bonus_expectation_bounds():
    """Projected means stay within the attainable envelope: race points plus
    the pole/FL bonus expectation can never exceed the per-round ceiling."""
    points = {c: 0.0 for c in ("AAA", "BBB", "CCC")}
    skill = {"AAA": 89.0, "BBB": 90.0, "CCC": 91.0}
    remaining = 3
    proj = model.project_championship_fe(points, skill, remaining_rounds=remaining, n_samples=300)
    ceiling = remaining * (
        max(config.POINTS.values()) + config.POLE_POINTS + config.FASTEST_LAP_POINTS
    )
    assert sum(t.p_title for t in proj) == pytest.approx(1.0)
    for t in proj:
        assert 0.0 <= t.proj_mean <= ceiling
    # The fastest driver carries the bonus expectation: mean above pure P1s-only
    # race points is allowed, but must respect the ceiling.
    best = max(proj, key=lambda t: t.proj_mean)
    assert best.key == "AAA"
