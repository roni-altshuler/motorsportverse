"""The FIA WEC website data contract: wec.json + per-round probability files.

Everything the site reads is keyed by class (endurance is scored per class), so
the export carries per-class standings / championship / next-round prediction and
a per-class + overall season-accuracy block. Kept fast by reducing the Monte-Carlo
sample count for the duration of the export.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")

from wec_predictions import config, export


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    orig = config.DEFAULT_SAMPLES
    config.DEFAULT_SAMPLES = 1500  # speed; shapes are sample-count-independent
    try:
        out = tmp_path_factory.mktemp("wecdata")
        export.write(out)
    finally:
        config.DEFAULT_SAMPLES = orig
    return out


def _load(path):
    return json.loads(path.read_text())


def test_wec_json_top_level_shape(data_dir):
    wec = _load(data_dir / "wec.json")
    assert wec["sport"] == config.SPORT
    assert isinstance(wec["classes"], list) and wec["classes"], "no classes exported"
    class_keys = [c["key"] for c in wec["classes"]]
    for c in wec["classes"]:
        assert {"key", "label", "color"} <= set(c)

    # per-class standings + championship for every regular-season class
    assert set(wec["standings"]) == set(class_keys)
    assert set(wec["championship"]) == set(class_keys)
    for cls in class_keys:
        for row in wec["standings"][cls]:
            assert {"position", "code", "points", "wins", "podiums"} <= set(row)
        champ = wec["championship"][cls]
        assert "entries" in champ and "remainingRounds" in champ
        for e in champ["entries"]:
            assert "pTitle" in e and "code" in e


def test_next_prediction_and_season_accuracy(data_dir):
    wec = _load(data_dir / "wec.json")
    pred = wec["nextPrediction"]
    assert pred is not None, "no next-round prediction exported"
    assert pred["classes"], "next prediction has no classes"
    for cls in pred["classes"]:
        assert cls["race"], "empty class race board"
        for row in cls["race"]:
            assert "pWin" in row and "pPodium" in row

    acc = wec["seasonAccuracy"]
    assert "overall" in acc and "byClass" in acc
    assert {"roundsScored", "winnerHitRate", "podiumHitRate"} <= set(acc["overall"])


def test_probability_files_win_market_sums_to_one(data_dir):
    prob_dir = data_dir / "probabilities"
    files = sorted(prob_dir.glob("round_*.json"))
    assert files, "no per-round probability files written"
    for path in files:
        payload = _load(path)
        for cls in payload["classes"]:
            win = cls["markets"]["win"]
            total = sum(v["probability"] for v in win.values())
            assert abs(total - 1.0) < 0.02, f"{path.name}/{cls['class']} win market sum={total:.3f}"
