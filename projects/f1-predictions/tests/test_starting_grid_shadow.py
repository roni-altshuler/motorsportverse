"""Final-grid contract regressions; Singapore data is a read-only diagnostic.

The flat model outputs below isolate grid coupling. They are test controls,
not forecasts, fitted models, or evidence of prediction accuracy.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from f1_prediction_utils import (
    DEFAULT_FEATURE_COLS, _parse_laptime_to_seconds, _zscore,
    apply_qualifying_data, apply_race_postprocessing, circuit_grid_dynamics,
)
from models.race_projection_head import DEFAULT_HEAD_FEATURES
from models.race_simulator import _RaceState, race_context_from_circuit
from models.race_simulator_runner import _build_grid_and_initials, run_simulator_for_round
from models.starting_grid import StartingGridEvent, StartingGridSnapshot, StartingGridUnavailable

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/starting-grid"
PAYLOAD = json.loads((FIXTURES / "rounds/round_17.json").read_text())
SOURCE = "https://www.formula1.com/en/results/2026/races/1296/singapore/starting-grid"
CUTOFF = "2026-10-11T06:00:00Z"  # retrospective contract check, never a forecast timestamp
CALENDAR = {r["round"]: {"gp_key": r["gpKey"], "name": r["name"], "circuit": r["circuit"],
                         "date": r["date"], "circuit_id": r["circuitId"],
                         "race_start_utc": r.get("raceStartUtc")}
            for r in json.loads((FIXTURES / "season.json").read_text())["calendar"]}
EVENT = StartingGridEvent.from_calendar(
    2026, 17, CALENDAR, race_start_utc="2026-10-11T12:00:00Z", source_url=SOURCE,
)


def grid_session(payload):
    return next(s for s in payload["weekendResults"]["sessions"] if s["key"] == "startingGrid")


def snapshot(payload=None, **kwargs):
    return StartingGridSnapshot.from_published(
        payload or PAYLOAD, event=EVENT,
        expected_drivers=[r["driver"] for r in grid_session(PAYLOAD)["rows"]],
        input_cutoff=kwargs.pop("input_cutoff", CUTOFF), **kwargs,
    )


def qualifying_frame():
    rows = next(s for s in PAYLOAD["weekendResults"]["sessions"] if s["key"] == "qualifying")["rows"]
    base = pd.DataFrame({"Driver": [r["driver"] for r in rows], "Team": [r["team"] for r in rows],
                         "CleanAirPace": 99.0, "WetPerformance": 1.0})
    times = {r["driver"]: _parse_laptime_to_seconds(r.get("time")) for r in rows}
    frame = apply_qualifying_data(base, times, grid_positions={r["driver"]: r["position"] for r in rows})
    for col, value in {"PredictedLapTime": 95.0, "PredictedLapTime_GB": 95.0,
                       "PredictedLapTime_XGB": 95.0, "CurrentForm": 0.0, "SkillPrior": 10.0,
                       "PositionTrend": 0.0, "ConsistencyScore": 0.1, "PitTimeLoss": 22.0,
                       "TyreDegFactor": 0.5, "SeasonMomentum": 0.0}.items():
        frame[col] = value
    return frame


@pytest.fixture(autouse=True)
def no_registry_writes(monkeypatch):
    monkeypatch.setenv("F1_REGISTRY_ENABLED", "0")
    monkeypatch.delenv("F1_USE_LEARNED_HEAD", raising=False)


def test_final_grid_is_separate_and_keeps_no_time_qualifying_semantics():
    original = qualifying_frame()
    result = snapshot().attach(original)
    pd.testing.assert_frame_equal(result[original.columns], original)
    russell = result.set_index("Driver").loc["RUS"]
    assert russell["QualifyingRank"] == 6
    assert russell["StartingGridPosition"] == 21
    assert russell["QualifyingTime"] == pytest.approx(91.747)
    hadjar = result.set_index("Driver").loc["HAD"]
    assert hadjar["QualifyingDataMissing"]
    assert hadjar["QualifyingRank"] == hadjar["StartingGridPosition"] == 22
    assert "StartingGridPosition" not in DEFAULT_FEATURE_COLS
    assert "StartingGridPosition" not in DEFAULT_HEAD_FEATURES
    assert "StartingGridPosition" not in original
    with pytest.raises(FrozenInstanceError):
        snapshot().positions = ()


def test_penalty_reaches_the_grid_prior_without_changing_qualifying_features():
    frame = qualifying_frame()
    legacy = apply_race_postprocessing(frame, circuit_key="Singapore")
    corrected = apply_race_postprocessing(
        frame, circuit_key="Singapore", shadow_starting_grid=snapshot(),
        shadow_event=EVENT, shadow_input_cutoff=CUTOFF,
    )
    pd.testing.assert_frame_equal(corrected[frame.columns], legacy[frame.columns])
    lock, _ = circuit_grid_dynamics(0.4, 0.8, 0.0, circuit_key="Singapore")
    expected_delta = (_zscore(corrected["StartingGridPosition"]) - _zscore(frame["QualifyingRank"])) * lock
    np.testing.assert_allclose(corrected["RaceProjectionScore"] - legacy["RaceProjectionScore"], expected_delta)
    old = legacy.set_index("Driver"); new = corrected.set_index("Driver")
    assert new.loc["RUS", "RaceProjectionScore"] > old.loc["RUS", "RaceProjectionScore"]
    assert new["RaceProjectionTime"].rank().loc["RUS"] > old["RaceProjectionTime"].rank().loc["RUS"]
    assert corrected.attrs["startingGridShadow"] == snapshot().provenance()


def test_grid_prior_does_not_activate_from_an_unverified_column():
    frame = qualifying_frame()
    frame["StartingGridPosition"] = frame["Driver"].map(dict(snapshot().positions))
    baseline = apply_race_postprocessing(frame.drop(columns="StartingGridPosition"), circuit_key="Singapore")
    actual = apply_race_postprocessing(frame, circuit_key="Singapore")
    pd.testing.assert_series_equal(actual["RaceProjectionScore"], baseline["RaceProjectionScore"])


def test_penalty_reaches_simulator_initial_position_and_retirement_prior():
    frame = qualifying_frame()
    old_grid, old_initials = _build_grid_and_initials(frame)
    grid, initials = _build_grid_and_initials(frame, shadow_starting_grid=snapshot())
    assert next(g.grid_position for g in old_grid if g.driver == "RUS") == 6
    assert next(g.grid_position for g in grid if g.driver == "RUS") == 21
    assert initials["RUS"].p_dnf > old_initials["RUS"].p_dnf
    assert initials["RUS"].base_pace_offset_s == old_initials["RUS"].base_pace_offset_s
    context = race_context_from_circuit(2026, 17, "Singapore", 2, {"Singapore": {}}, None)
    state = _RaceState(grid, context, initials, {}, np.random.default_rng(42))
    assert state.position[[g.driver for g in grid].index("RUS")] == 21
    assert [g.grid_position for g in grid] == list(range(1, 23))


def test_simulator_shadow_carries_exact_event_and_cutoff_provenance(monkeypatch):
    seen = {}
    reg = SimpleNamespace(
        list_all=lambda: [(2025, 99, {"kind": "race-pace"})],
        load=lambda *_: {"race_pace_gbr": object(), "race_pace_xgb": object()},
    )
    monkeypatch.setattr("models.race_simulator_runner.registry_enabled", lambda: True)
    monkeypatch.setattr("models.race_simulator_runner.ModelRegistry", lambda: reg)

    def fake_simulator(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(n_samples=1, n_laps=2, p_win={}, p_podium={}, p_top6={}, p_top10={}, mean_finish_position={})

    monkeypatch.setattr("models.race_simulator_runner.simulate_race", fake_simulator)
    result = run_simulator_for_round(
        2026, 17, "Singapore", qualifying_frame(), None, 2, {"Singapore": {}},
        shadow_starting_grid=snapshot(), shadow_input_cutoff=CUTOFF,
    )
    assert result["mode"] == "starting-grid-shadow"
    assert result["starting_grid_provenance"] == snapshot().provenance()
    assert next(g.grid_position for g in seen["grid"] if g.driver == "RUS") == 21
    assert seen["context"].season == 2026 and seen["context"].round_num == 17


@pytest.mark.parametrize("mutation,reason", [
    ("missing", "missing-final-grid"), ("ambiguous", "ambiguous-final-grid"),
    ("wrong-round", "published-event-mismatch"), ("wrong-circuit", "published-event-mismatch"),
    ("wrong-date", "published-event-mismatch"), ("wrong-season", "published-season-mismatch"),
    ("wrong-source", "unverified-final-grid-source"), ("estimated", "unverified-final-grid-source"),
    ("provider-identity", "provider-event-mismatch"), ("missing-driver", "incomplete-final-grid-field"),
    ("duplicate-driver", "duplicate-grid-driver"), ("duplicate-position", "invalid-grid-positions"),
    ("pit-lane-zero", "invalid-grid-positions"), ("fractional-position", "invalid-grid-positions"),
    ("bool-position", "invalid-grid-positions"), ("unknown-driver", "incomplete-final-grid-field"),
    ("naive-time", "invalid-source-verification"), ("missing-time", "invalid-source-verification"),
    ("future-time", "source-verified-after-cutoff"), ("stale-time", "stale-source-verification"),
    ("future-publication", "published-source-generated-after-cutoff"),
    ("fetched-later", "source-fetched-after-verification"), ("malformed-rows", "invalid-grid-rows"),
])
def test_missing_invalid_or_stale_grid_is_explicit(mutation, reason):
    data = deepcopy(PAYLOAD); session = grid_session(data)
    if mutation == "missing": data["weekendResults"]["sessions"].remove(session)
    elif mutation == "ambiguous": data["weekendResults"]["sessions"].append(deepcopy(session))
    elif mutation == "wrong-round": data["round"] = 16
    elif mutation == "wrong-circuit": data["circuit"] = "Sepang International Circuit"
    elif mutation == "wrong-date": data["date"] = "2026-10-04"
    elif mutation == "wrong-season": data["season"] = 2025
    elif mutation == "wrong-source": session["sourceUrl"] = SOURCE.replace("singapore", "bahrain")
    elif mutation == "estimated": session["status"] = "estimated"
    elif mutation == "provider-identity": session["eventIdentity"] = {**EVENT.identity(), "circuitId": "sepang"}
    elif mutation == "missing-driver": session["rows"].pop()
    elif mutation == "duplicate-driver": session["rows"].append(deepcopy(session["rows"][0]))
    elif mutation == "duplicate-position": session["rows"][1]["position"] = 1
    elif mutation == "pit-lane-zero": session["rows"][-1]["position"] = 0
    elif mutation == "fractional-position": session["rows"][0]["position"] = 1.5
    elif mutation == "bool-position": session["rows"][0]["position"] = True
    elif mutation == "unknown-driver": session["rows"][0]["driver"] = "ZZZ"
    elif mutation == "naive-time": session["verifiedAt"] = "2026-10-11T05:15:33"
    elif mutation == "missing-time": session.pop("verifiedAt")
    elif mutation == "future-time": session["verifiedAt"] = "2026-10-11T06:00:01Z"
    elif mutation == "stale-time": session["verifiedAt"] = "2026-10-11T04:59:59Z"
    elif mutation == "future-publication": data["weekendResults"]["generatedAt"] = "2026-10-11T06:00:01Z"
    elif mutation == "fetched-later": session["fetchedAt"] = "2026-10-11T05:16:00Z"
    elif mutation == "malformed-rows": session["rows"] = [None]
    with pytest.raises(StartingGridUnavailable) as exc:
        snapshot(data)
    assert exc.value.reason == reason


@pytest.mark.parametrize("cutoff", ["2026-10-11T12:00:00Z", "2026-10-11T12:00:01Z"])
def test_race_start_is_a_hard_boundary(cutoff):
    with pytest.raises(StartingGridUnavailable, match="cutoff-not-before-race"):
        snapshot(input_cutoff=cutoff)


def test_shadow_context_and_reused_cutoff_fail_before_simulator_fallback():
    with pytest.raises(StartingGridUnavailable, match="shadow-event-mismatch"):
        run_simulator_for_round(2026, 16, "Singapore", qualifying_frame(), None, 2, {},
                                shadow_starting_grid=snapshot(), shadow_input_cutoff=CUTOFF)
    with pytest.raises(StartingGridUnavailable, match="shadow-cutoff-mismatch"):
        run_simulator_for_round(2026, 17, "Singapore", qualifying_frame(), None, 2, {},
                                shadow_starting_grid=snapshot(), shadow_input_cutoff="2026-10-11T07:00:00Z")
    with pytest.raises(StartingGridUnavailable, match="invalid-requested-input-cutoff"):
        run_simulator_for_round(2026, 17, "Singapore", qualifying_frame(), None, 2, {},
                                shadow_starting_grid=snapshot())


def test_shadow_postprocessor_refuses_other_event_and_unevaluated_learned_head(monkeypatch):
    with pytest.raises(StartingGridUnavailable, match="shadow-event-mismatch"):
        apply_race_postprocessing(qualifying_frame(), "Singapore", shadow_starting_grid=snapshot(),
                                 shadow_event=replace(EVENT, round_num=18), shadow_input_cutoff=CUTOFF)
    monkeypatch.setenv("F1_USE_LEARNED_HEAD", "1")
    with pytest.raises(StartingGridUnavailable, match="learned-head-grid-contract-not-evaluated"):
        apply_race_postprocessing(qualifying_frame(), "Singapore", shadow_starting_grid=snapshot(),
                                 shadow_event=EVENT, shadow_input_cutoff=CUTOFF)


def test_frame_subset_or_contradictory_column_cannot_fall_back_to_qualifying():
    frame = qualifying_frame()
    with pytest.raises(StartingGridUnavailable, match="shadow-frame-field-mismatch"):
        _build_grid_and_initials(frame.iloc[:-1], shadow_starting_grid=snapshot())
    frame["StartingGridPosition"] = frame["QualifyingRank"]
    with pytest.raises(StartingGridUnavailable, match="contradictory-starting-grid-column"):
        snapshot().attach(frame)


def test_cutoff_timezones_normalize_and_source_age_policy_is_bounded():
    assert snapshot(input_cutoff="2026-10-11T08:00:00+02:00").input_cutoff == datetime(2026, 10, 11, 6, tzinfo=timezone.utc)
    with pytest.raises(StartingGridUnavailable, match="invalid-source-age-policy"):
        snapshot(max_source_age=timedelta(0))
    with pytest.raises(StartingGridUnavailable, match="invalid-source-age-policy"):
        snapshot(max_source_age=timedelta(hours=2))


def test_reusing_old_source_for_a_new_cutoff_is_explicitly_stale():
    with pytest.raises(StartingGridUnavailable, match="stale-source-verification"):
        snapshot(input_cutoff="2026-10-11T09:00:00Z")


def test_offline_audit_reports_actual_temporal_coverage_without_prediction_claims():
    from audit_starting_grid_contract import build_report
    report = build_report(FIXTURES, season=2026, round_num=17,
                          source_url=SOURCE, race_start_utc="2026-10-11T12:00:00Z", input_cutoff=CUTOFF)
    assert report["completedRoundCount"] == 16
    assert report["completedRoundsWithFinalGridSession"] == report["eligibleTemporalEvaluationRounds"] == 0
    assert all(r["reason"] == "missing-published-round" for r in report["temporalCoverage"])
    assert not report["predictionAccuracyEvaluated"] and not report["newForecastGenerated"]
    assert not report["servingWrites"] and not report["publicationHoldReleased"]
    russell = next(r for r in report["penaltyInputDiagnostics"] if r["driver"] == "RUS")
    assert russell["qualifyingRank"] == 6 and russell["simulatorInitialPosition"] == 21


def test_audit_cli_refuses_to_overwrite_the_published_receipt():
    receipt = ROOT / "website/public/data/baselines/2026_round_17.json"
    before = receipt.read_bytes()
    result = subprocess.run([
        sys.executable, str(ROOT / "src/audit_starting_grid_contract.py"),
        "--round", "17", "--source-url", SOURCE, "--race-start-utc", "2026-10-11T12:00:00Z",
        "--input-cutoff", CUTOFF, "--output", str(receipt),
    ], capture_output=True, text=True)
    assert result.returncode == 2
    assert "never published/model state" in result.stderr
    assert receipt.read_bytes() == before


def test_preview_without_official_qualifying_fails_explicitly():
    from audit_starting_grid_contract import _controlled_frame
    preview = deepcopy(PAYLOAD)
    preview.pop("weekendResults")
    with pytest.raises(StartingGridUnavailable, match="unverified-qualifying-source"):
        _controlled_frame(preview, EVENT)
