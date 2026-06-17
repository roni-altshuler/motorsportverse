"""Sanity invariants the F2 forecasts and exported JSON must always satisfy."""

import json
import math

import pytest

from f2_predictions import config, export, model
from f2_predictions.datasource import F2DataSource


@pytest.fixture
def source():
    return F2DataSource()


@pytest.fixture
def forecast(source):
    return model.forecast_round(source, config.SEASON, config.COMPLETED_ROUNDS + 1, n_samples=3000)


def test_each_race_is_a_full_permutation(forecast):
    codes = sorted(d["code"] for d in config.DRIVERS)
    for race in (forecast.sprint, forecast.feature):
        assert sorted(race.order) == codes
        assert sorted(g for g in race.grid) == codes
        assert len(set(race.grid)) == 22  # no duplicate grid slots


def test_probabilities_are_well_formed(forecast):
    for race in (forecast.sprint, forecast.feature):
        m = race.markets
        assert abs(sum(m.p_win.values()) - 1.0) < 1e-6
        for code in race.order:
            # Cumulative markets are monotonic and free of NaN.
            for v in (m.p_win[code], m.p_podium[code], m.p_top6[code], m.p_top10[code]):
                assert not math.isnan(v)
            assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


def test_exported_rounds_are_complete(tmp_path):
    export.write(tmp_path)
    files = sorted((tmp_path / "rounds").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        rj = json.loads(f.read_text())
        for race_type in ("sprint", "feature"):
            block = rj[race_type]
            assert len(block["classification"]) == 22
            positions = [e["position"] for e in block["classification"]]
            assert positions == list(range(1, 23))


def test_completed_rounds_have_actuals_upcoming_do_not(tmp_path):
    export.write(tmp_path)
    completed = json.loads((tmp_path / "rounds" / "round_01.json").read_text())
    upcoming = json.loads(
        (tmp_path / "rounds" / f"round_{config.COMPLETED_ROUNDS + 1:02d}.json").read_text()
    )
    assert completed["completed"] is True
    assert "accuracy" in completed["feature"]
    assert upcoming["completed"] is False
    assert all(e["actualPosition"] is None for e in upcoming["feature"]["classification"])
