"""Tests for the drift-detection module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import drift_report
from models.drift import (
    BRIER_MODERATE_REGRESSION,
    BRIER_SIGNIFICANT_REGRESSION,
    PSI_MODERATE_THRESHOLD,
    PSI_SIGNIFICANT_THRESHOLD,
    build_health_report,
    classify_psi,
    feature_drift_report,
    population_stability_index,
    rolling_brier_trend,
)


# --------------------------------------------------------------------------- #
# PSI
# --------------------------------------------------------------------------- #


class TestPopulationStabilityIndex:
    def test_identical_distributions_give_psi_near_zero(self):
        rng_values = list(range(100))
        psi = population_stability_index(rng_values, rng_values)
        assert psi < PSI_MODERATE_THRESHOLD

    def test_disjoint_distributions_give_high_psi(self):
        baseline = [0.0] * 50
        current = [100.0] * 50
        psi = population_stability_index(baseline, current)
        # Disjoint values land in different bins → PSI well above the
        # "significant" threshold.
        assert psi > PSI_SIGNIFICANT_THRESHOLD

    def test_empty_input_returns_zero(self):
        assert population_stability_index([], [1.0, 2.0]) == 0.0
        assert population_stability_index([1.0, 2.0], []) == 0.0

    def test_n_bins_below_two_raises(self):
        with pytest.raises(ValueError, match="n_bins"):
            population_stability_index([1.0, 2.0], [3.0, 4.0], n_bins=1)

    def test_nan_values_filtered(self):
        baseline = [1.0, float("nan"), 2.0, 3.0, None]
        current = [1.5, 2.5, 3.5, 4.5]
        # Should run without crashing — NaN / None are dropped.
        psi = population_stability_index(baseline, current)
        assert isinstance(psi, float)
        assert psi >= 0


class TestClassifyPSI:
    @pytest.mark.parametrize(
        ("psi", "expected"),
        [
            (0.0, "ok"),
            (0.09, "ok"),
            (PSI_MODERATE_THRESHOLD, "warn"),
            (0.20, "warn"),
            (PSI_SIGNIFICANT_THRESHOLD, "alarm"),
            (1.0, "alarm"),
        ],
    )
    def test_band_thresholds(self, psi: float, expected: str):
        assert classify_psi(psi) == expected


class TestFeatureDriftReport:
    def test_skips_missing_or_non_numeric_features(self):
        baseline = [{"predictedTime": 80.0, "team": "RB"}]
        current = [{"team": "MCL"}]  # missing predictedTime
        summaries = feature_drift_report(baseline, current, ["predictedTime"])
        # No current numeric values → no summary
        assert summaries == []

    def test_returns_one_summary_per_feature(self):
        baseline = [{"a": float(i), "b": float(i * 2)} for i in range(20)]
        current = [{"a": float(i), "b": float(i * 2)} for i in range(20)]
        summaries = feature_drift_report(baseline, current, ["a", "b"])
        assert {s.feature for s in summaries} == {"a", "b"}
        # Identical → PSI near zero → severity "ok"
        for s in summaries:
            assert s.severity == "ok"


# --------------------------------------------------------------------------- #
# Rolling Brier
# --------------------------------------------------------------------------- #


class TestRollingBrierTrend:
    def test_returns_ok_when_not_enough_rounds(self):
        # Window=5 needs 10 rounds; supplying 6
        series = [(i, 0.20) for i in range(1, 7)]
        summary = rolling_brier_trend(series, window=5)
        assert summary.severity == "ok"
        assert summary.rolling_brier_baseline is None

    def test_stable_brier_is_ok(self):
        # 12 rounds of consistent 0.20 Brier
        series = [(i, 0.20) for i in range(1, 13)]
        summary = rolling_brier_trend(series, window=5)
        assert summary.severity == "ok"
        assert summary.relative_change == pytest.approx(0.0)

    def test_moderate_regression_is_warn(self):
        # First 6 rounds: 0.20; last 6 rounds: 0.22 → +10% regression
        series = [(i, 0.20) for i in range(1, 7)] + [(i, 0.22) for i in range(7, 13)]
        summary = rolling_brier_trend(series, window=5)
        assert summary.severity == "warn"
        assert BRIER_MODERATE_REGRESSION <= summary.relative_change < BRIER_SIGNIFICANT_REGRESSION

    def test_significant_regression_is_alarm(self):
        # +25% Brier regression
        series = [(i, 0.20) for i in range(1, 7)] + [(i, 0.25) for i in range(7, 13)]
        summary = rolling_brier_trend(series, window=5)
        assert summary.severity == "alarm"
        assert summary.relative_change >= BRIER_SIGNIFICANT_REGRESSION

    def test_handles_unsorted_input(self):
        series = [(5, 0.20), (2, 0.20), (1, 0.20)]
        # Should sort internally; result deterministic regardless of order
        summary = rolling_brier_trend(series, window=2)
        assert summary.rounds_compared == 3
        assert summary.rolling_brier_recent == pytest.approx(0.20)


# --------------------------------------------------------------------------- #
# Top-level builder
# --------------------------------------------------------------------------- #


class TestBuildHealthReport:
    def test_collects_warnings_and_alarms_correctly(self):
        # Synthetic baseline / current with a feature that drifts hard:
        baseline = [{"score": float(i)} for i in range(20)]
        current = [{"score": float(i + 100)} for i in range(20)]
        report = build_health_report(
            season=2026,
            last_evaluated_round=4,
            baseline_records=baseline,
            current_records=current,
            feature_columns=["score"],
            brier_by_round=[],
        )
        assert report.season == 2026
        assert report.last_evaluated_round == 4
        # That feature drift triggers an alarm
        assert len(report.alarms) >= 1
        assert any("score" in a for a in report.alarms)

    def test_no_warnings_when_distributions_match(self):
        records = [{"score": float(i)} for i in range(20)]
        report = build_health_report(
            season=2026,
            last_evaluated_round=4,
            baseline_records=records,
            current_records=records,
            feature_columns=["score"],
            brier_by_round=[(i, 0.20) for i in range(1, 13)],
        )
        assert report.alarms == []
        assert report.output_drift is not None
        assert report.output_drift.severity == "ok"


# --------------------------------------------------------------------------- #
# CLI integration (drift_report.py)
# --------------------------------------------------------------------------- #


class TestDriftReportCLI:
    def test_handles_missing_directories_with_allow_empty(self, tmp_path: Path):
        out = tmp_path / "model_health.json"
        # Use directories that don't exist
        rc = drift_report.main(
            [
                "--season",
                "2026",
                "--rounds-dir",
                str(tmp_path / "rounds-does-not-exist"),
                "--forward-eval-dir",
                str(tmp_path / "fe-does-not-exist"),
                "--output",
                str(out),
                "--allow-empty",
                "--quiet",
            ]
        )
        assert rc == 0

    def test_writes_report_with_synthetic_round_data(self, tmp_path: Path):
        rounds_dir = tmp_path / "rounds"
        fe_dir = tmp_path / "fe"
        rounds_dir.mkdir()
        fe_dir.mkdir()
        # Two rounds of synthetic classification data
        for rnd, mean_time in ((1, 80.0), (2, 82.0)):
            (rounds_dir / f"round_{rnd:02d}.json").write_text(
                json.dumps(
                    {
                        "round": rnd,
                        "classification": [
                            {
                                "driver": f"D{i}",
                                "predictedTime": mean_time + i * 0.1,
                                "winProbability": 0.05,
                                "finishRangeLow": i + 1,
                                "finishRangeHigh": i + 3,
                            }
                            for i in range(20)
                        ],
                    }
                )
            )
            (fe_dir / f"round_{rnd:02d}.json").write_text(
                json.dumps(
                    {
                        "round": rnd,
                        "rmse_position_error": 0.20 + 0.005 * rnd,
                    }
                )
            )
        out = tmp_path / "model_health.json"
        rc = drift_report.main(
            [
                "--season",
                "2026",
                "--rounds-dir",
                str(rounds_dir),
                "--forward-eval-dir",
                str(fe_dir),
                "--output",
                str(out),
                "--quiet",
            ]
        )
        assert rc == 0
        assert out.exists()
        with out.open() as fh:
            payload = json.load(fh)
        assert payload["season"] == 2026
        assert payload["lastEvaluatedRound"] == 2
        assert "featureDrift" in payload
        assert "outputDrift" in payload
        assert isinstance(payload["brierByRound"], list)
        assert len(payload["brierByRound"]) == 2
