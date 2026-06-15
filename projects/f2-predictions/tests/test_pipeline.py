"""Tests for the F2 product pipeline — every new capability is covered."""

import json

import pytest

from f2_predictions import config, export, pipeline
from f2_predictions.datasource import F2DataSource


@pytest.fixture
def source():
    return F2DataSource()


# --------------------------------------------------------------------------- #
# Calendar ingestion + roster
# --------------------------------------------------------------------------- #
def test_calendar_and_completed_rounds(source):
    season = source.season(config.SEASON)
    assert len(season.calendar) == len(config.CALENDAR)
    assert season.completed_rounds == list(range(1, config.COMPLETED_ROUNDS + 1))


def test_completed_round_has_two_races(source):
    races = source.race_results_for_round(config.SEASON, 1)
    assert len(races["sprint"]) == 22
    assert len(races["feature"]) == 22
    # positions are a complete permutation 1..22
    assert sorted(r.position for r in races["feature"]) == list(range(1, 23))


def test_future_round_has_no_results(source):
    assert source.results(config.SEASON, config.COMPLETED_ROUNDS + 1) == []


def test_results_are_deterministic(source):
    a = [r.competitor for r in source.results(config.SEASON, 2, race_index=1)]
    b = [r.competitor for r in source.results(config.SEASON, 2, race_index=1)]
    assert a == b


# --------------------------------------------------------------------------- #
# Standings (driver + team)
# --------------------------------------------------------------------------- #
def test_driver_standings(source):
    table = pipeline.driver_standings(source, config.SEASON)
    assert len(table) == 22
    # monotonically non-increasing points
    pts = [r.points for r in table]
    assert pts == sorted(pts, reverse=True)
    # every driver raced sprint+feature across all completed rounds
    assert table[0].rounds == config.COMPLETED_ROUNDS * 2


def test_team_standings(source):
    table = pipeline.team_standings(source, config.SEASON)
    assert len(table) == len(config.TEAMS)
    pts = [r.points for r in table]
    assert pts == sorted(pts, reverse=True)


def test_team_points_equal_sum_of_driver_points(source):
    drivers = pipeline.driver_standings(source, config.SEASON)
    teams = pipeline.team_standings(source, config.SEASON)
    assert sum(d.points for d in drivers) == pytest.approx(sum(t.points for t in teams))


# --------------------------------------------------------------------------- #
# Pace estimation is leakage-safe
# --------------------------------------------------------------------------- #
def test_estimate_pace_uses_only_prior_rounds(source):
    pace = pipeline.estimate_pace(source, config.SEASON, current_round=4)
    assert len(pace) == 22
    assert all(v > 0 for v in pace.values())


def test_estimate_pace_round_one_is_neutral(source):
    # no prior rounds -> neutral pace for everyone
    pace = pipeline.estimate_pace(source, config.SEASON, current_round=1)
    assert len(set(pace.values())) == 1


# --------------------------------------------------------------------------- #
# Qualifying + race prediction
# --------------------------------------------------------------------------- #
def test_predict_round_shapes(source):
    pred = pipeline.predict_round(source, config.SEASON, config.COMPLETED_ROUNDS + 1)
    assert len(pred.qualifying_order) == 22
    assert len(pred.race_order) == 22
    assert set(pred.qualifying_order) == set(pred.race_order)
    assert abs(sum(pred.p_win.values()) - 1.0) < 1e-6
    # podium prob >= win prob for everyone
    assert all(pred.p_podium[c] >= pred.p_win[c] - 1e-9 for c in pred.race_order)


# --------------------------------------------------------------------------- #
# Championship Monte Carlo
# --------------------------------------------------------------------------- #
def test_championship_projection(source):
    proj = pipeline.project_title(source, config.SEASON, n_samples=1500)
    assert len(proj) == 22
    assert abs(sum(p.p_title for p in proj) - 1.0) < 1e-6
    assert proj == sorted(proj, key=lambda p: -p.p_title)
    # projected mean points >= current points (more races to come)
    assert all(p.proj_mean >= p.current_points - 1e-6 for p in proj)


# --------------------------------------------------------------------------- #
# Export contract
# --------------------------------------------------------------------------- #
def test_export_payload_is_valid_json(tmp_path):
    path = export.write(tmp_path)
    data = json.loads(path.read_text())
    assert data["sport"] == "Formula 2"
    assert len(data["driverStandings"]) == 22
    assert len(data["teamStandings"]) == len(config.TEAMS)
    assert len(data["championship"]) == 22
    assert data["nextPrediction"]["round"] == config.COMPLETED_ROUNDS + 1
    assert len(data["calendar"]) == len(config.CALENDAR)
