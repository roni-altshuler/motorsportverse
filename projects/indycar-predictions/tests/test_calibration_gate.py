"""The honest calibration gate: only REAL rounds count, and the export says so."""
from __future__ import annotations

from indycar_predictions import config, export, pipeline
from indycar_predictions.datasource import IndycarDataSource
from indycar_predictions.sources.synthetic import SyntheticIndycarSource

SEASON = config.SEASON


def test_gate_closed_on_synthetic_only():
    source = IndycarDataSource(source=SyntheticIndycarSource())
    calibrator, real_rounds = export.build_calibrator(source, SEASON)
    assert calibrator is None
    assert real_rounds == 0


def test_gate_closed_below_threshold(truncated_source, monkeypatch):
    """6 real rounds are required; a 6-round season is exactly at the gate,
    so tighten the threshold to prove the gate reads the config."""
    monkeypatch.setattr(config, "MIN_REAL_ROUNDS_FOR_CALIBRATION", 10)
    calibrator, real_rounds = export.build_calibrator(truncated_source, SEASON)
    assert calibrator is None
    assert real_rounds == 6


def test_gate_open_on_real_snapshot(real_source):
    calibrator, real_rounds = export.build_calibrator(real_source, SEASON)
    assert real_rounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    assert calibrator is not None and calibrator.is_fitted()
    # Track-type strata: 11 completed rounds cover all three types.
    strata = calibrator.strata_with_models()
    assert set(strata) & set(config.TRACK_TYPES)


def test_probabilities_payload_honest_reason(truncated_source):
    fc = pipeline.forecast_round(truncated_source, SEASON, 7)
    payload = export.probabilities_payload(fc, None, 2)
    assert payload["calibration"]["applied"] is False
    assert "awaiting" in payload["calibration"]["reason"]
    win = payload["race"]["markets"]["win"]
    assert all("rawProbability" in v for v in win.values())
    # The hazard rides alongside the markets.
    assert payload["race"]["dnf"]


def test_calibrated_payload_keeps_raw_alongside(real_source):
    calibrator, real_rounds = export.build_calibrator(real_source, SEASON)
    fc = pipeline.forecast_round(real_source, SEASON, 12)
    payload = export.probabilities_payload(fc, calibrator, real_rounds)
    assert payload["calibration"]["applied"] is True
    win = payload["race"]["markets"]["win"]
    assert all(set(v) == {"probability", "rawProbability"} for v in win.values())


def test_calibration_summary_shapes(real_source):
    calibrator, real_rounds = export.build_calibrator(real_source, SEASON)
    summary = export._calibration_summary(calibrator, real_rounds)
    assert summary["applied"] is True
    assert summary["trainingRounds"] == real_rounds
    assert set(summary["perMarket"]) == {"win", "podium", "top6", "top10"}
    assert all(n > 0 for n in summary["perMarket"].values())
