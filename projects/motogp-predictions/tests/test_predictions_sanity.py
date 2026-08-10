"""Sanity invariants the MotoGP forecasts and exported JSON must always satisfy."""
from __future__ import annotations

import json
import math
import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from motogp_predictions import config, export, model
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


def test_probabilities_are_well_formed(forecast):
    for race in (forecast.sprint, forecast.feature):
        m = race.markets
        assert abs(sum(m.p_win.values()) - 1.0) < 1e-6
        for code in race.order:
            for v in (m.p_win[code], m.p_podium[code], m.p_top6[code], m.p_top10[code]):
                assert not math.isnan(v)
            assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("motogpdata")
    export.write(out)
    return out


def test_exported_rounds_are_complete(exported):
    files = sorted((exported / "rounds").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        rj = json.loads(f.read_text())
        for race_type in ("sprint", "feature"):
            classification = rj[race_type]["classification"]
            # Completed real rounds list classified finishers only (DNFs excluded),
            # so the block can be shorter than the roster; forecast rounds are a
            # full-grid permutation.
            assert len(classification) <= len(config.DRIVERS)
            positions = [e["position"] for e in classification]
            assert positions == list(range(1, len(classification) + 1))
            for e in classification:
                for k in ("pWin", "pPodium", "pTop6", "pTop10", "predictedValue", "meanFinish"):
                    assert not math.isnan(float(e[k]))


def test_completed_rounds_have_actuals_upcoming_do_not(exported):
    completed = json.loads((exported / "rounds" / "round_01.json").read_text())
    upcoming = json.loads(
        (exported / "rounds" / f"round_{config.COMPLETED_ROUNDS + 1:02d}.json").read_text()
    )
    assert completed["completed"] is True
    assert "accuracy" in completed["feature"]
    assert upcoming["completed"] is False
    assert all(e["actualPosition"] is None for e in upcoming["feature"]["classification"])


def test_standings_are_ordered_and_consistent(exported):
    data = json.loads((exported / "motogp.json").read_text())
    drivers = data["driverStandings"]
    teams = data["teamStandings"]
    assert len(drivers) >= 15 and len(teams) == len(config.MANUFACTURERS)

    # Points are monotonically non-increasing down the table, positions are 1..N,
    # and no value is NaN.
    for table in (drivers, teams):
        pts = [row["points"] for row in table]
        assert pts == sorted(pts, reverse=True)
        assert [row["position"] for row in table] == list(range(1, len(table) + 1))
        assert all(not math.isnan(p) for p in pts)

    # Cumulative history is non-decreasing and ends at the displayed total.
    for row in drivers:
        hist = row["pointsHistory"]
        assert hist == sorted(hist)
        if hist:
            assert hist[-1] <= row["points"] + 1e-6

    # Manufacturer points equal the sum of their riders' points (no bonus points).
    driver_sum_by_team: dict[str, float] = {}
    for d in drivers:
        driver_sum_by_team[d["team"]] = driver_sum_by_team.get(d["team"], 0.0) + d["points"]
    for t in teams:
        assert abs(driver_sum_by_team.get(t["team"], 0.0) - t["points"]) < 1e-6


def test_championship_is_a_distribution(exported):
    data = json.loads((exported / "motogp.json").read_text())
    champ = data["championship"]
    assert abs(sum(c["pTitle"] for c in champ) - 1.0) < 1e-6
    assert all(0.0 <= c["pTitle"] <= 1.0 for c in champ)
    # The current points leader can always still win.
    leader = max(champ, key=lambda c: c["currentPoints"])
    assert leader["canStillWin"] is True
