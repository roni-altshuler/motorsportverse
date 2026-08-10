"""Sanity invariants the WRC forecasts and exported JSON must always satisfy."""
from __future__ import annotations

import json
import math
import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from wrc_predictions import config, export, model
from wrc_predictions.datasource import WrcDataSource


@pytest.fixture
def source():
    return WrcDataSource()


@pytest.fixture
def forecast(source):
    return model.forecast_round(source, config.SEASON, config.COMPLETED_ROUNDS, n_samples=3000)


def test_rally_is_a_full_permutation(forecast):
    codes = sorted(d["code"] for d in config.DRIVERS)
    assert sorted(forecast.rally.order) == codes


def test_probabilities_are_well_formed(forecast):
    m = forecast.rally.markets
    assert abs(sum(m.p_win.values()) - 1.0) < 1e-6  # win normalised to a coherent market
    for code in forecast.rally.order:
        for v in (m.p_win[code], m.p_podium[code], m.p_top6[code], m.p_top10[code]):
            assert not math.isnan(v)
        assert m.p_top10[code] >= m.p_top6[code] >= m.p_podium[code] >= m.p_win[code] - 1e-9


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("wrcdata")
    export.write(out)
    return out


def test_exported_rounds_are_complete(exported):
    files = sorted((exported / "rounds").glob("round_*.json"))
    assert len(files) == len(config.CALENDAR)
    for f in files:
        rj = json.loads(f.read_text())
        rally = rj["rally"]
        # A rally forecast is a full-field permutation (all crews ranked), for both
        # completed and upcoming rounds; completed rounds carry actualPosition too.
        classification = rally["classification"]
        assert len(classification) == len(config.DRIVERS)
        positions = [e["position"] for e in classification]
        assert positions == list(range(1, len(classification) + 1))
        assert rally["surface"] in config.SURFACE_COLORS
        for e in classification:
            for k in ("pWin", "pPodium", "pTop6", "pTop10", "predictedValue", "meanFinish"):
                assert not math.isnan(float(e[k]))


def test_completed_rounds_have_actuals_upcoming_do_not(exported):
    completed = json.loads((exported / "rounds" / "round_01.json").read_text())
    upcoming = json.loads(
        (exported / "rounds" / f"round_{config.COMPLETED_ROUNDS + 1:02d}.json").read_text()
    )
    assert completed["completed"] is True
    assert "accuracy" in completed["rally"]
    assert upcoming["completed"] is False
    assert all(e["actualPosition"] is None for e in upcoming["rally"]["classification"])


def test_standings_are_ordered_and_consistent(exported):
    data = json.loads((exported / "wrc.json").read_text())
    drivers = data["driverStandings"]
    manufacturers = data["manufacturerStandings"]
    assert len(drivers) >= 15 and len(manufacturers) >= 1

    for table in (drivers, manufacturers):
        pts = [row["points"] for row in table]
        assert pts == sorted(pts, reverse=True)
        assert [row["position"] for row in table] == list(range(1, len(table) + 1))
        assert all(not math.isnan(p) for p in pts)

    # Cumulative history is non-decreasing and ends at/under the displayed total
    # (the real per-round points reconcile exactly with the official season total).
    for row in drivers:
        hist = row["pointsHistory"]
        assert hist == sorted(hist)
        if hist:
            assert hist[-1] <= row["points"] + 1e-6


def test_championship_is_a_distribution(exported):
    data = json.loads((exported / "wrc.json").read_text())
    champ = data["championship"]
    # pTitle is rounded to 4 dp in the export, so the sum carries rounding error;
    # the exact distribution is asserted on the unrounded projection elsewhere.
    assert abs(sum(c["pTitle"] for c in champ) - 1.0) < 1e-3
    assert all(0.0 <= c["pTitle"] <= 1.0 for c in champ)
    # The current points leader can always still win.
    leader = max(champ, key=lambda c: c["currentPoints"])
    assert leader["canStillWin"] is True


def test_next_prediction_carries_surface(exported):
    data = json.loads((exported / "wrc.json").read_text())
    nxt = data["nextPrediction"]
    if nxt is not None:  # None only if the season is complete
        assert nxt["surface"] in config.SURFACE_COLORS
        assert len(nxt["rally"]) == len(config.DRIVERS)
