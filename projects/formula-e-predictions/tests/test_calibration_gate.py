"""The honest calibration gate: only REAL rounds count, and the export says so."""
from __future__ import annotations

from formula_e_predictions import config, export, model, pipeline
from formula_e_predictions.datasource import FEDataSource
from formula_e_predictions.sources.synthetic import SyntheticFESource

SEASON = config.SEASON


def test_gate_closed_on_synthetic_only():
    source = FEDataSource(source=SyntheticFESource())
    calibrator, real_rounds = export.build_calibrator(source, SEASON)
    assert calibrator is None
    assert real_rounds == 0


def test_gate_open_on_real_snapshot(real_source):
    calibrator, real_rounds = export.build_calibrator(real_source, SEASON)
    assert real_rounds >= config.MIN_REAL_ROUNDS_FOR_CALIBRATION
    assert calibrator is not None and calibrator.is_fitted()
    # Venue-kind strata: 2025-26's 13 completed rounds cover both kinds.
    strata = calibrator.strata_with_models()
    assert "street" in strata
    assert "win" in strata["street"]


def test_probabilities_payload_honest_reason(truncated_source):
    fc = pipeline.forecast_round(truncated_source, SEASON, 6)
    payload = export.probabilities_payload(fc, None, 2)
    assert payload["calibration"]["applied"] is False
    assert "awaiting" in payload["calibration"]["reason"]
    # Raw MC probabilities are always present, calibrated or not.
    win = payload["race"]["markets"]["win"]
    assert all("rawProbability" in v for v in win.values())


def test_calibrated_payload_keeps_raw_alongside(real_source):
    calibrator, real_rounds = export.build_calibrator(real_source, SEASON)
    fc = pipeline.forecast_round(real_source, SEASON, 14)
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


def test_street_variance_not_clamped(real_source):
    """The model must NOT hand-clamp street-circuit variance — the spread of
    its raw probabilities should be venue-agnostic (the calibrator owns the
    correction). Guard: forecasts exist for both kinds with full markets."""
    street = model.forecast_round(real_source, SEASON, 9)    # Monaco
    circuit = model.forecast_round(real_source, SEASON, 12)  # Shanghai
    for fc in (street, circuit):
        assert len(fc.race.markets.p_win) == 20
        assert max(fc.race.markets.p_win.values()) > min(fc.race.markets.p_win.values())
