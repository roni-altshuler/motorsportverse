"""The Cup model: skill blend, track-type Elo, DNF composition, grid conditioning."""
from __future__ import annotations

import numpy as np

from nascar_predictions import config, model

SEASON = config.SEASON


def test_estimate_skill_covers_entrants_and_is_deterministic(real_source):
    pace1 = model.estimate_skill(real_source, SEASON, 8)
    pace2 = model.estimate_skill(real_source, SEASON, 8)
    assert pace1 == pace2
    entrants = set(real_source.entrants(SEASON, 8))
    assert set(pace1) == entrants
    assert len(set(round(p, 6) for p in pace1.values())) > 5  # real spread


def test_incremental_elo_matches_fresh_replay(real_source):
    """Walking rounds forward incrementally must equal a from-scratch replay."""
    from nascar_predictions.datasource import NascarDataSource

    # Warm a source incrementally: 5 then 9.
    model.estimate_skill(real_source, SEASON, 5)
    incremental = model.estimate_skill(real_source, SEASON, 9)
    # Fresh source straight to 9.
    fresh = NascarDataSource()
    scratch = model.estimate_skill(fresh, SEASON, 9)
    assert incremental == scratch


def test_track_type_elo_differentiates_specialists(real_source):
    """The per-track-type Elo must actually differ from the overall rating —
    a road-course forecast should not reduce to the oval form ranking."""
    stack = model._elo_skill(real_source, SEASON, 20)
    road = stack["track"]["road"]
    overall = stack["driver"]
    common = [c for c in road if c in overall and road[c] != 1500.0]
    assert len(common) >= 20
    road_order = sorted(common, key=lambda c: -road[c])
    overall_order = sorted(common, key=lambda c: -overall[c])
    assert road_order != overall_order


def test_dnf_risk_bounds_and_track_effect(real_source):
    """Superspeedway hazard must exceed road-course hazard (pack racing)."""
    lo, hi = config.DNF_CLIP
    r20 = model.estimate_dnf_risk(real_source, SEASON, 20)  # Atlanta superspeedway
    r18 = model.estimate_dnf_risk(real_source, SEASON, 18)  # Sonoma road
    for p in list(r20.values()) + list(r18.values()):
        assert lo <= p <= hi
    mean20 = sum(r20.values()) / len(r20)
    mean18 = sum(r18.values()) / len(r18)
    assert mean20 > mean18


def test_dnf_composition_sanity_hazard_up_finish_down():
    """First-class DNF head: raising ONE driver's hazard must worsen his
    expected finish and cut his win probability — with pace held fixed."""
    codes = [f"D{i:02d}" for i in range(20)]
    pace = {c: 90.0 + 0.05 * i for i, c in enumerate(codes)}
    target = codes[2]  # a front-runner
    low = {c: 0.05 for c in codes}
    high = dict(low)
    high[target] = 0.35
    fc_low = model._race_forecast("race", codes, pace, low, n_samples=4000)
    fc_high = model._race_forecast("race", codes, pace, high, n_samples=4000)
    assert fc_high.mean_finish[target] > fc_low.mean_finish[target] + 1.0
    assert fc_high.markets.p_win[target] < fc_low.markets.p_win[target]
    # Everyone else benefits or stays flat.
    others_low = np.mean([fc_low.mean_finish[c] for c in codes if c != target])
    others_high = np.mean([fc_high.mean_finish[c] for c in codes if c != target])
    assert others_high <= others_low


def test_composed_markets_are_coherent(real_source):
    fc = model.forecast_round(real_source, SEASON, 20)
    m = fc.race.markets
    assert abs(sum(m.p_win.values()) - 1.0) < 1e-6
    assert abs(sum(m.p_podium.values()) - 3.0) < 1e-6
    for c in m.p_win:
        assert m.p_win[c] <= m.p_podium[c] + 1e-9
        assert m.p_podium[c] <= m.p_top6[c] + 1e-9
        assert m.p_top6[c] <= m.p_top10[c] + 1e-9
    # DNF hazard rides on the forecast for the probability layer.
    assert set(fc.race.p_dnf) == set(m.p_win)
    # H2H is symmetric-complementary.
    a, b = fc.race.order[0], fc.race.order[1]
    assert abs(m.h2h[a][b] + m.h2h[b][a] - 1.0) < 1e-9


def test_zero_hazard_reduces_to_pure_plackett_luce():
    """With hazard 0 the composed sampler must reproduce the core sampler's
    probabilities (same Gumbel-max math)."""
    from motorsport_core import calibration

    codes = [f"D{i:02d}" for i in range(12)]
    pace = {c: 90.0 + 0.08 * i for i, c in enumerate(codes)}
    fc = model._race_forecast("race", codes, pace, {c: 0.0 for c in codes}, n_samples=5000)
    core = calibration.plackett_luce_probabilities(pace, n_samples=5000)
    for c in codes:
        assert abs(fc.markets.p_win[c] - core.p_win[c]) < 0.02


def test_known_grid_conditions_forecast(real_source):
    pace = model.estimate_skill(real_source, SEASON, 20)
    merit = sorted(pace, key=lambda c: pace[c])
    reversed_grid = list(reversed(merit))
    fc_pre = model.forecast_round(real_source, SEASON, 20)
    fc_post = model.forecast_round(real_source, SEASON, 20, known_grid=reversed_grid)
    assert fc_post.race.grid == reversed_grid
    # Putting the fastest driver at the back must hurt his expected finish.
    fastest = merit[0]
    assert fc_post.race.mean_finish[fastest] > fc_pre.race.mean_finish[fastest]


def test_round_forecast_metadata(real_source):
    fc = model.forecast_round(real_source, SEASON, 8)
    assert fc.track_type == "short"
    assert fc.venue_name == "Bristol Motor Speedway"
    assert fc.race_name == "Food City 500"
    assert fc.position_head is None  # gate OFF by default


def test_regular_season_projection_includes_stage_expectation():
    codes = [f"D{i:02d}" for i in range(10)]
    skill = {c: 90.0 + 0.05 * i for i, c in enumerate(codes)}
    proj = model.project_regular_season_points({c: 0.0 for c in codes}, skill, 4,
                                               n_samples=500)
    best = proj[0]
    # Ceiling per race incl. stages: 55 + 2*10 = 75; floor: > race-only mean.
    assert best.proj_mean <= 4 * 75.0
    assert best.proj_mean > 4 * 30.0
