"""Tests for the forward_eval calibration extension."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from forward_eval import (
    evaluate_calibration,
    load_round_probabilities,
    write_reliability_plots,
)


def _write_probability_file(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def test_load_round_probabilities_filters_by_round(tmp_path):
    _write_probability_file(
        tmp_path / "round_01.json",
        {"round": 1, "classification": []},
    )
    _write_probability_file(
        tmp_path / "round_02.json",
        {"round": 2, "classification": []},
    )
    out = load_round_probabilities(tmp_path, season=2026, rounds=[2])
    assert set(out.keys()) == {2}


def test_evaluate_calibration_skips_rounds_without_actuals():
    probs = {
        1: {
            "round": 1,
            "classification": [
                {"driver": "VER", "p_win": 0.5, "p_podium": 0.8},
                {"driver": "NOR", "p_win": 0.3, "p_podium": 0.7},
            ],
        }
    }
    actual: dict[int, dict[str, int]] = {}  # no actuals yet
    report = evaluate_calibration(2026, probs, actual)
    assert report.by_market == {}


def test_evaluate_calibration_basic_metrics():
    probs = {
        1: {
            "round": 1,
            "classification": [
                {"driver": "VER", "p_win": 0.6, "p_podium": 0.9, "p_top6": 0.95, "p_top10": 0.99},
                {"driver": "NOR", "p_win": 0.2, "p_podium": 0.6, "p_top6": 0.8, "p_top10": 0.95},
                {"driver": "PIA", "p_win": 0.1, "p_podium": 0.4, "p_top6": 0.7, "p_top10": 0.9},
            ],
        }
    }
    actual = {1: {"VER": 1, "NOR": 2, "PIA": 5}}
    report = evaluate_calibration(2026, probs, actual)
    assert {"win", "podium", "top6", "top10"} <= set(report.by_market.keys())
    win_m = report.by_market["win"]
    assert win_m.n_samples == 3
    # Brier is bounded [0, 1].
    assert 0.0 <= win_m.brier <= 1.0


def test_write_reliability_plots_emits_pngs(tmp_path):
    from models.reliability import compute_calibration_metrics

    p = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    y = [0, 0, 0, 1, 0, 1, 1, 1, 1]
    metrics = compute_calibration_metrics(p, y)
    from models.reliability import MarketReliabilityReport

    report = MarketReliabilityReport(by_market={"win": metrics})
    paths = write_reliability_plots(report, tmp_path)
    assert len(paths) == 1
    assert paths[0].suffix == ".png"
    assert paths[0].exists()
