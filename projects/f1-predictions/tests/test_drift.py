"""Tests for the drift-detection module."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import drift_report
from models.drift import (
    RMSE_MODERATE_REGRESSION,
    RMSE_SIGNIFICANT_REGRESSION,
    PSI_MODERATE_THRESHOLD,
    PSI_SIGNIFICANT_THRESHOLD,
    build_health_report,
    classify_psi,
    feature_drift_report,
    population_stability_index,
    rolling_rmse_trend,
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
# Rolling RMSE
# --------------------------------------------------------------------------- #


class TestRollingRMSETrend:
    def test_returns_ok_when_not_enough_rounds(self):
        # Window=5 needs 10 rounds; supplying 6
        series = [(i, 0.20) for i in range(1, 7)]
        summary = rolling_rmse_trend(series, window=5)
        assert summary.severity == "insufficient_history"
        assert summary.rolling_rmse_baseline is None

    def test_stable_rmse_is_ok(self):
        # 12 rounds of consistent 0.20 RMSE
        series = [(i, 0.20) for i in range(1, 13)]
        summary = rolling_rmse_trend(series, window=5)
        assert summary.severity == "ok"
        assert summary.relative_change == pytest.approx(0.0)

    def test_moderate_regression_is_warn(self):
        # First 6 rounds: 0.20; last 6 rounds: 0.22 → +10% regression
        series = [(i, 0.20) for i in range(1, 7)] + [(i, 0.22) for i in range(7, 13)]
        summary = rolling_rmse_trend(series, window=5)
        assert summary.severity == "warn"
        assert RMSE_MODERATE_REGRESSION <= summary.relative_change < RMSE_SIGNIFICANT_REGRESSION

    def test_significant_regression_is_alarm(self):
        # +25% RMSE regression
        series = [(i, 0.20) for i in range(1, 7)] + [(i, 0.25) for i in range(7, 13)]
        summary = rolling_rmse_trend(series, window=5)
        assert summary.severity == "alarm"
        assert summary.relative_change >= RMSE_SIGNIFICANT_REGRESSION

    def test_handles_unsorted_input(self):
        series = [(5, 0.20), (2, 0.20), (1, 0.20)]
        # Should sort internally; result deterministic regardless of order
        summary = rolling_rmse_trend(series, window=2)
        assert summary.rounds_compared == 3
        assert summary.rolling_rmse_recent == pytest.approx(0.20)


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
            rmse_by_round=[],
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
            rmse_by_round=[(i, 0.20) for i in range(1, 13)],
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
        payload = json.loads(out.read_text())
        assert payload["diagnosticStatus"] == "no_eligible_rounds"
        assert payload["alarms"] == []

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
                        "name": f"GP {rnd}", "gpKey": f"GP{rnd}",
                        "circuit": f"Circuit {rnd}", "date": f"2026-01-{rnd:02}",
                        "actualResults": {f"D{i}": i + 3 for i in range(20)},
                        "classification": [
                            {
                                "driver": f"D{i}", "position": i + 1,
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
                        "season": 2026, "drivers_compared": 20,
                        "rmse_position_error": 2.0,
                    }
                )
            )
        (tmp_path / "season.json").write_text(json.dumps({
            "season": 2026, "calendar": [
                {"round": r, "name": f"GP {r}", "gpKey": f"GP{r}",
                 "circuit": f"Circuit {r}", "date": f"2026-01-{r:02}"}
                for r in (1, 2)
            ]
        }))
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
        assert isinstance(payload["rmseByRound"], list)
        assert len(payload["rmseByRound"]) == 2


@pytest.fixture
def diagnostic_inputs(tmp_path):
    rounds, grades = tmp_path / "rounds", tmp_path / "forward_eval"
    rounds.mkdir()
    grades.mkdir()
    calendar = []

    def write(rnd, *, held=False, settled=True, event_date="2026-01-01", score=2.0):
        event = {"round": rnd, "name": f"GP {rnd}", "gpKey": f"GP{rnd}",
                 "circuit": f"Circuit {rnd}", "date": event_date}
        calendar.append(event)
        state = {**event, "classification": [{"driver": "D", "position": 1 + score if type(score) in (int, float) else 1, "predictedTime": float(rnd)}],
                 "actualResults": {"D": 1} if settled else {}}
        if held:
            state["publicationHold"] = {"reason": "event-mismatch"}
        (rounds / f"round_{rnd:02}.json").write_text(json.dumps(state))
        (grades / f"round_{rnd:02}.json").write_text(json.dumps({
            "season": 2026, "round": rnd, "drivers_compared": 1, "rmse_position_error": score,
        }))
        (tmp_path / "season.json").write_text(json.dumps({"season": 2026, "calendar": calendar}))

    def report():
        return drift_report.report_to_jsonable(drift_report.build_report(
            2026, rounds, grades, rolling_window=1, today=date(2026, 10, 13),
        ))
    return write, report, rounds, grades


def test_future_filename_and_stale_grade_are_excluded(diagnostic_inputs):
    write, report, _, _ = diagnostic_inputs
    write(1)
    write(2)
    write(23, event_date="2026-12-06", score=999)
    payload = report()
    assert payload["lastEvaluatedRound"] == 2
    assert payload["lastObservedRound"] == 2
    assert payload["rmseByRound"] == [{"round": 1, "rmse": 2.0}, {"round": 2, "rmse": 2.0}]
    assert payload["excludedRounds"] == [{"round": 23, "reason": "future_round"}]


@pytest.mark.parametrize("settled", [True, False])
def test_latest_held_round_clears_all_diagnostics_even_with_stale_grade(diagnostic_inputs, settled):
    write, report, _, _ = diagnostic_inputs
    write(1)
    write(2, score=20)
    write(17, held=True, settled=settled)
    write(23, event_date="2026-12-06")
    payload = report()
    assert payload["diagnosticStatus"] == "publication_hold"
    assert payload["lastObservedRound"] == 17
    assert payload["lastEvaluatedRound"] is None
    assert payload["featureDrift"] == payload["rmseByRound"] == []
    assert payload["outputDrift"] is None
    assert payload["alarms"] == payload["warnings"] == []


def test_held_round_is_not_baseline_when_a_later_eligible_round_exists(diagnostic_inputs):
    write, report, _, _ = diagnostic_inputs
    write(1)
    write(2, held=True, score=999)
    write(3)
    payload = report()
    assert payload["diagnosticStatus"] == "available"
    assert payload["lastEvaluatedRound"] == 3
    assert [r["round"] for r in payload["rmseByRound"]] == [1, 3]
    assert payload["featureDrift"][0]["baseline_n"] == 1


def test_settled_metrics_are_position_rmse_with_honest_alarm_labels(diagnostic_inputs):
    write, report, _, _ = diagnostic_inputs
    write(1)
    write(2, score=4)
    payload = report()
    assert payload["outputMetric"] == "rmse_position_error"
    assert payload["outputUnit"] == "positions"
    assert payload["outputDrift"]["rolling_rmse_recent"] == 4
    assert any("position RMSE regression" in a for a in payload["alarms"])
    assert "brier" not in json.dumps(payload).lower()


@pytest.mark.parametrize("score", [None, -1, float("nan"), float("inf"), "bad", True])
def test_invalid_grades_do_not_create_health_claims(diagnostic_inputs, score):
    write, report, _, _ = diagnostic_inputs
    write(1, score=score)
    payload = report()
    assert payload["diagnosticStatus"] == "no_eligible_rounds"
    assert payload["lastEvaluatedRound"] is None
    assert payload["outputDrift"] is None
    assert payload["alarms"] == []


@pytest.mark.parametrize("kind", ["unsettled", "wrong_season", "wrong_event", "missing_calendar", "no_forecast", "wrong_grade_round"])
def test_ineligible_inputs_fail_closed(diagnostic_inputs, kind):
    write, report, rounds, grades = diagnostic_inputs
    write(1, settled=kind != "unsettled")
    if kind in ("wrong_season", "wrong_grade_round"):
        p = grades / "round_01.json"
        d = json.loads(p.read_text())
        d["season" if kind == "wrong_season" else "round"] = 2025
        p.write_text(json.dumps(d))
    elif kind in ("wrong_event", "no_forecast"):
        p = rounds / "round_01.json"
        d = json.loads(p.read_text())
        d["name" if kind == "wrong_event" else "classification"] = "Wrong GP" if kind == "wrong_event" else []
        p.write_text(json.dumps(d))
    elif kind == "missing_calendar":
        (rounds.parent / "season.json").unlink()
    payload = report()
    assert payload["diagnosticStatus"] == "no_eligible_rounds"
    assert payload["alarms"] == []


@pytest.mark.parametrize("field", ["round", "name", "gpKey", "circuit", "date"])
@pytest.mark.parametrize("side", ["calendar", "snapshot", "both"])
@pytest.mark.parametrize("value", ["missing", None, "", " \t", 7, [], {}, True])
def test_incomplete_or_invalid_identity_is_ineligible(diagnostic_inputs, field, side, value):
    write, report, rounds, _ = diagnostic_inputs
    write(1)
    paths = []
    if side in ("calendar", "both"):
        paths.append(rounds.parent / "season.json")
    if side in ("snapshot", "both"):
        paths.append(rounds / "round_01.json")
    for path in paths:
        data = json.loads(path.read_text())
        identity = data["calendar"][0] if path.name == "season.json" else data
        if value == "missing":
            identity.pop(field)
        else:
            identity[field] = value
        path.write_text(json.dumps(data))
    payload = report()
    assert payload["diagnosticStatus"] == "no_eligible_rounds"
    assert payload["lastEvaluatedRound"] is None
    assert payload["featureDrift"] == payload["rmseByRound"] == []
    assert payload["outputDrift"] is None
    assert payload["alarms"] == payload["warnings"] == []


@pytest.mark.parametrize("round_value", [True, 1.0, 0, -1, "1"])
def test_snapshot_round_requires_a_positive_integer(diagnostic_inputs, round_value):
    write, report, rounds, _ = diagnostic_inputs
    write(1)
    path = rounds / "round_01.json"
    data = json.loads(path.read_text())
    data["round"] = round_value
    path.write_text(json.dumps(data))
    assert report()["diagnosticStatus"] == "no_eligible_rounds"


@pytest.mark.parametrize("season_value", [2026.0, "2026", True, None, 0, -1])
def test_calendar_season_requires_a_positive_integer(diagnostic_inputs, season_value):
    write, report, rounds, _ = diagnostic_inputs
    write(1)
    path = rounds.parent / "season.json"
    data = json.loads(path.read_text())
    data["season"] = season_value
    path.write_text(json.dumps(data))
    assert report()["diagnosticStatus"] == "no_eligible_rounds"


def test_complete_canonical_identity_remains_eligible_without_rewriting_inputs(diagnostic_inputs):
    write, report, rounds, grades = diagnostic_inputs
    write(1)
    write(2)
    paths = [rounds.parent / "season.json", *rounds.glob("*.json"), *grades.glob("*.json")]
    before = {path: path.read_bytes() for path in paths}
    payload = report()
    assert payload["diagnosticStatus"] == "available"
    assert payload["lastEvaluatedRound"] == payload["lastObservedRound"] == 2
    assert [entry["round"] for entry in payload["rmseByRound"]] == [1, 2]
    assert payload["excludedRounds"] == []
    assert {path: path.read_bytes() for path in paths} == before


@pytest.mark.parametrize("event_date", ["20260101", "2026-02-30", "2026-01-01T00:00:00"])
def test_identity_date_requires_canonical_calendar_date(diagnostic_inputs, event_date):
    write, report, _, _ = diagnostic_inputs
    write(1, event_date=event_date)
    assert report()["diagnosticStatus"] == "no_eligible_rounds"


@pytest.mark.parametrize("field", ["name", "gpKey", "circuit"])
def test_partial_identity_cannot_release_latest_elapsed_hold(diagnostic_inputs, field):
    write, report, rounds, _ = diagnostic_inputs
    write(1)
    write(2, score=20)
    write(3, held=True)
    for path in (rounds.parent / "season.json", rounds / "round_03.json"):
        data = json.loads(path.read_text())
        identity = data["calendar"][-1] if path.name == "season.json" else data
        identity.pop(field)
        path.write_text(json.dumps(data))
    payload = report()
    assert payload["diagnosticStatus"] == "publication_hold"
    assert payload["lastObservedRound"] == 3
    assert payload["featureDrift"] == payload["rmseByRound"] == []
    assert payload["outputDrift"] is None
    assert payload["alarms"] == payload["warnings"] == []


def test_noncanonical_date_cannot_release_latest_elapsed_hold(diagnostic_inputs):
    write, report, _, _ = diagnostic_inputs
    write(1)
    write(2, held=True, event_date="20260101")
    payload = report()
    assert payload["diagnosticStatus"] == "publication_hold"
    assert payload["lastObservedRound"] == 2
    assert payload["alarms"] == payload["warnings"] == []


def test_allow_empty_overwrites_stale_alarm_report(tmp_path):
    output = tmp_path / "model_health.json"
    output.write_text('{"alarms": ["stale"], "lastEvaluatedRound": 23}')
    rc = drift_report.main(["--season", "2026", "--rounds-dir", str(tmp_path / "missing"),
                            "--forward-eval-dir", str(tmp_path / "missing-fe"),
                            "--output", str(output), "--allow-empty", "--quiet"])
    assert rc == 0
    payload = json.loads(output.read_text())
    assert payload["alarms"] == []
    assert payload["lastEvaluatedRound"] is None
    assert payload["diagnosticStatus"] == "no_eligible_rounds"


def test_insufficient_history_is_not_stable_and_uses_actual_mean():
    summary = rolling_rmse_trend([(1, 2), (2, 4)], window=5)
    assert summary.severity == "insufficient_history"
    assert summary.rolling_rmse_recent == 3
    assert summary.relative_change is None


def test_zero_baseline_cannot_claim_stable_when_error_increases():
    summary = rolling_rmse_trend([(1, 0), (2, 2)], window=1)
    assert summary.severity == "insufficient_baseline"
    assert summary.relative_change is None


def test_invalid_rolling_window_is_rejected():
    with pytest.raises(ValueError, match="window"):
        rolling_rmse_trend([], window=0)


def test_held_event_mismatch_still_suppresses_current_diagnostics(diagnostic_inputs):
    write, report, rounds, _ = diagnostic_inputs
    write(1)
    write(2, score=20)
    write(3, held=True)
    p = rounds / "round_03.json"
    d = json.loads(p.read_text())
    d["name"] = "Wrong GP"
    p.write_text(json.dumps(d))
    payload = report()
    assert payload["diagnosticStatus"] == "publication_hold"
    assert payload["lastObservedRound"] == 3
    assert payload["alarms"] == []


@pytest.mark.parametrize("calendar", [[], None, [], {"calendar": None}, {"calendar": [None]},
                                    {"calendar": [{}]}, {"calendar": ["bad"]}])
def test_malformed_season_data_writes_unavailable_instead_of_retaining_alarms(tmp_path, calendar):
    (tmp_path / "season.json").write_text(json.dumps(calendar))
    out = tmp_path / "health.json"
    out.write_text('{"alarms":["stale"]}')
    rc = drift_report.main(["--season", "2026", "--rounds-dir", str(tmp_path / "rounds"),
                           "--forward-eval-dir", str(tmp_path / "fe"), "--output", str(out),
                           "--allow-empty", "--quiet"])
    assert rc == 0
    assert json.loads(out.read_text())["alarms"] == []


@pytest.mark.parametrize("kind", ["actual_string", "classification_string", "boolean_count", "changed_result", "changed_forecast"])
def test_malformed_or_stale_grades_are_ineligible(diagnostic_inputs, kind):
    write, report, rounds, grades = diagnostic_inputs
    write(1)
    p = (grades if kind == "boolean_count" else rounds) / "round_01.json"
    d = json.loads(p.read_text())
    if kind == "actual_string": d["actualResults"] = "bad"
    elif kind == "classification_string": d["classification"] = "bad"
    elif kind == "boolean_count": d["drivers_compared"] = True
    elif kind == "changed_result": d["actualResults"]["D"] = 20
    else: d["classification"][0]["position"] = 20
    p.write_text(json.dumps(d))
    payload = report()
    assert payload["diagnosticStatus"] == "no_eligible_rounds"
    assert payload["alarms"] == []
