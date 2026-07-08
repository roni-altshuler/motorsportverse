"""Pipeline orchestration tests: standings, points, title projection."""
from __future__ import annotations

import pytest

from formula_e_predictions import config, pipeline
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.synthetic import SyntheticFESource

SEASON = config.SEASON


def test_official_standings_only_when_real(real_source):
    official = pipeline.official_standings(real_source, SEASON)
    assert official is not None
    assert official["driverStandings"][0]["points"] > 0

    synthetic = FEDataSource(source=SyntheticFESource())
    assert pipeline.official_standings(synthetic, SEASON) is None


def test_current_points_match_official_exactly(real_source):
    """The championship's current points must equal the official table
    (bonuses included) — never a recomputed approximation."""
    pts = pipeline.current_driver_points(real_source, SEASON)
    official = pipeline.official_standings(real_source, SEASON)
    for d in official["driverStandings"]:
        assert pts[d["code"]] == d["points"]


def test_recomputed_standings_on_synthetic():
    source = FEDataSource(source=SyntheticFESource())
    rows = pipeline.driver_standings(source, SEASON)
    assert len(rows) == 20
    assert rows[0].points >= rows[-1].points
    teams = pipeline.team_standings(source, SEASON)
    assert len(teams) == 10


def test_predict_round_compact_view(real_source):
    rp = pipeline.predict_round(real_source, SEASON, 14)
    assert rp.round == 14
    assert len(rp.race_order) == 20
    assert set(rp.p_win) == set(rp.race_order)


def test_project_title_probabilities_sum(real_source):
    proj = pipeline.project_title(real_source, SEASON, n_samples=500)
    assert sum(t.p_title for t in proj) == pytest.approx(1.0, abs=1e-6)
    # Projections start from the official current points.
    pts = pipeline.current_driver_points(real_source, SEASON)
    for t in proj:
        assert t.current_points == pts.get(t.key, 0.0)
        assert t.proj_mean >= t.current_points - 1e-9


def test_estimate_pace_covers_roster(real_source):
    pace = pipeline.estimate_pace(real_source, SEASON, 14)
    assert set(pace) == {d["code"] for d in config.DRIVERS}
    assert all(80.0 < p < 100.0 for p in pace.values())
