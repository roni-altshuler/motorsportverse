"""Calendar insertions must not turn a valid round echo into a wrong-event grade."""
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

import f1_prediction_utils as fpu
import gp_weekend
import export_website_data as ew
from advanced_models import SeasonTracker
from event_identity import fastf1_matches, jolpica_matches

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "website/public/data"
CALENDAR = fpu.CALENDAR
PROVIDER = json.loads((ROOT / "docs/qa/event-identity/provider-calendar-2026.json").read_text())
RACES = {int(r["round"]): r for r in PROVIDER["MRData"]["RaceTable"]["Races"]}


@pytest.mark.parametrize("field,value", [
    ("season", "2025"), ("round", "16"), ("date", "2026-10-04"),
    ("raceName", "Bahrain Grand Prix in Malaysia"),
    ("Circuit", {"circuitId": "sepang"}), ("season", None),
    ("round", None), ("date", None), ("raceName", None), ("Circuit", {}),
])
def test_same_round_echo_cannot_hide_other_or_missing_identity(field, value):
    race = copy.deepcopy(RACES[17])
    race[field] = value
    assert not jolpica_matches(race, 2026, 17, CALENDAR)


def test_inserted_event_is_valid_but_not_a_singapore_fallback():
    assert jolpica_matches(RACES[16], 2026, 16, CALENDAR)
    assert jolpica_matches(RACES[17], 2026, 17, CALENDAR)
    stale = {16: dict(CALENDAR[17])}  # the exact old Singapore-round-16 calendar defect
    assert not jolpica_matches(RACES[16], 2026, 16, stale)


def test_fallback_rejects_sepang_even_when_it_echoes_requested_round(monkeypatch):
    import urllib.request
    stale = {16: dict(CALENDAR[17])}
    monkeypatch.setattr(fpu, "CALENDAR", stale)
    monkeypatch.setattr(fpu, "get_calendar", lambda _year: stale)
    race = {**RACES[16], "QualifyingResults": [
        {"position": "1", "Driver": {"code": "VER"}, "Q3": "1:30.123"}
    ]}
    payload = {"MRData": {"RaceTable": {"Races": [race]}}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: io.BytesIO(json.dumps(payload).encode()))
    assert fpu._fetch_qualifying_from_jolpica(2026, "Singapore", expected_round=16) is None


@pytest.mark.parametrize("field,value", [
    ("RoundNumber", 16), ("EventName", "Bahrain Grand Prix"),
    ("EventDate", "2026-10-04"), ("Location", "Kuala Lumpur"), ("Location", None),
])
def test_fastf1_verifies_name_date_and_venue_as_well_as_round(field, value):
    event = {"RoundNumber": 17, "EventName": "Singapore Grand Prix",
             "EventDate": "2026-10-11", "Location": "Marina Bay"}
    assert fastf1_matches(event, 17, CALENDAR)
    event[field] = value
    assert not fastf1_matches(event, 17, CALENDAR)


def test_provider_utc_date_and_fastf1_local_date_are_explicit_for_vegas():
    assert jolpica_matches(RACES[21], 2026, 21, CALENDAR)
    assert fastf1_matches({"RoundNumber": 21, "EventName": "Las Vegas Grand Prix",
                          "EventDate": "2026-11-21", "Location": "Las Vegas"}, 21, CALENDAR)


def test_all_verified_provider_calendar_identities_are_accepted():
    for rnd, race in RACES.items():
        assert jolpica_matches(race, 2026, rnd, CALENDAR), race["raceName"]
    records = json.loads((ROOT / "docs/qa/event-identity/fastf1-calendar-identities.json").read_text())["records"]
    for r in records:
        assert fastf1_matches({"RoundNumber": r["round"], "EventName": r["name"],
                              "EventDate": r["date"], "Location": r["location"]}, r["round"], CALENDAR)


def test_wrong_committed_actuals_cannot_make_a_poll_a_noop(monkeypatch):
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda _r: {
        "round": 16, "name": "Singapore Grand Prix", "gpKey": "Singapore",
        "circuit": "Marina Bay", "date": "2026-10-11", "actualResults": {"VER": 1},
        "gridProvenance": "real-quali-verified", "predictionPhase": "post-quali",
    })
    monkeypatch.setattr(gp_weekend, "_detect_phase", lambda _r: "post-race")
    assert gp_weekend.needs_update(16)


def test_withdrawn_forecast_cannot_count_as_final_verified_freeze(monkeypatch):
    state = json.loads((DATA / "rounds/round_17.json").read_text())
    monkeypatch.setattr(gp_weekend, "_committed_round_state", lambda _r: state)
    monkeypatch.setattr(gp_weekend, "_detect_phase", lambda _r: "post-quali")
    assert gp_weekend.needs_update(17)


def test_wrong_event_weekend_rows_never_get_an_official_badge(monkeypatch):
    race = {**RACES[16], "round": "17", "QualifyingResults": [
        {"position": "1", "Driver": {"code": "VER"}}
    ]}
    monkeypatch.setattr(ew, "_fetch_jolpica_json", lambda _p: {"MRData": {"RaceTable": {"Races": [race]}}})
    session = ew._fetch_jolpica_weekend_session(17, 2026, "qualifying", "qualifying", "Qualifying", "Q", "qualifying")
    assert session["status"] == "pending" and not session["rows"]
    assert session["eventIdentity"] is None
    assert ew._fetch_live_round_actual_results(17) is None


def test_withdrawn_snapshot_clears_a_previously_graded_tracker_row(tmp_path, monkeypatch):
    monkeypatch.setattr(SeasonTracker, "TRACKER_FILE", str(tmp_path / "tracker.json"))
    tracker = SeasonTracker()
    tracker.data = {"rounds": {"17": {"predicted": {"VER": {"position": 1}},
                                      "actual": {"VER": {"position": 1}}}},
                    "accuracy": {"17": {"accuracy_pct": 100}}}
    tracker.sync_from_round_file(17, json.loads((DATA / "rounds/round_17.json").read_text()))
    assert tracker.data["rounds"]["17"] == {"predicted": {}, "actual": {}}
    assert "17" not in tracker.data["accuracy"]


def test_withdrawn_forecast_replaces_previously_published_probabilities(tmp_path, monkeypatch):
    import export_probabilities as ep
    rounds = tmp_path / "rounds"
    probabilities = tmp_path / "probabilities"
    rounds.mkdir()
    probabilities.mkdir()
    (rounds / "round_17.json").write_text((DATA / "rounds/round_17.json").read_text())
    target = probabilities / "round_17.json"
    target.write_text('{"round":17,"drivers":[{"driver":"VER"}]}')
    monkeypatch.setattr(ep, "ROUNDS_DIR", rounds)
    monkeypatch.setattr(ep, "PROBS_DIR", probabilities)
    monkeypatch.setattr(ep, "_load_actuals", lambda: {})
    ep.run(rounds=[17], dry_run=True, quiet=True)
    assert target.exists()
    ep.run(rounds=[17], quiet=True)
    withdrawal = json.loads(target.read_text())
    assert withdrawal["status"] == "withheld"
    assert all(not entries for entries in withdrawal["markets"].values())
    assert not withdrawal["h2h"]
    assert not withdrawal["calibration"]["applied"]


@pytest.mark.parametrize("wrong_event", [False, True])
def test_completion_requires_actuals_and_matching_event(tmp_path, monkeypatch, wrong_event):
    import export_circuit_history as history
    state = json.loads((DATA / f"rounds/round_{17 if wrong_event else 16}.json").read_text())
    state["round"] = 16
    state["predictionPhase"] = "post-race"
    state["actualResults"] = {"VER": 1} if wrong_event else {}
    (tmp_path / "round_16.json").write_text(json.dumps(state))
    monkeypatch.setattr(ew, "ROUNDS_DIR", str(tmp_path))
    monkeypatch.setattr(ew, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ew, "_ensure_dirs", lambda: None)
    monkeypatch.setattr(ew, "_load_driver_nationality", lambda: {})
    monkeypatch.setattr(ew, "_write_seasons_index", lambda *_a: None)
    monkeypatch.setattr(history, "export_circuit_history", lambda: None)
    season = ew.export_season_metadata()
    assert 16 not in season["completedRounds"]
    assert 16 not in season["forecastRounds"]


def _old_event_state():
    state = json.loads((DATA / "rounds/round_17.json").read_text())
    state.update(name="United States Grand Prix", gpKey="United States",
                 circuit="Circuit of the Americas", date="2026-10-25")
    state.update(actualResults={"VER": 1}, accuracy={"accuracy_pct": 100},
                 gpReport={"round": 17}, trackerData={"rounds": [{"round": 17, "hasActual": True}]},
                 telemetryData={"from": "other event"}, strategyData={"from": "other event"})
    state["circuitInfo"]["geometry"] = {"path": "wrong-venue-outline"}
    return state


def test_post_quali_export_blocks_wrong_event_before_pipeline_or_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "round_17.json"
    original = json.dumps(_old_event_state())
    path.write_text(original)
    monkeypatch.setattr(ew, "ROUNDS_DIR", str(tmp_path))
    def pipeline_must_not_start():
        pytest.fail("wrong-event state reached regeneration before quarantine")
    monkeypatch.setattr(ew, "_ensure_dirs", pipeline_must_not_start)
    with pytest.raises(ValueError, match="quarantine"):
        ew.export_round_data(17, prediction_phase="post-quali")
    assert path.read_text() == original


def test_wrong_event_cannot_preserve_or_rehydrate_its_grade_from_tracker(monkeypatch):
    contaminated_tracker = {"rounds": {"17": {"actual": {"VER": {"position": 1}}}},
                            "accuracy": {"17": {"accuracy_pct": 100}}}
    monkeypatch.setattr(ew, "_safe_load_json", lambda _p: contaminated_tracker)
    assert ew._get_round_preserved_fields(17, _old_event_state()) == {}
    assert ew._get_round_preserved_fields(17, None) == {}


def test_same_event_preserves_actuals_and_enrichment_and_can_rehydrate_tracker(monkeypatch):
    state = json.loads((DATA / "rounds/round_17.json").read_text())
    state.update(actualResults={"VER": 1}, accuracy={"accuracy_pct": 50},
                 telemetryData={"same": "event"}, gpReport={"round": 17})
    monkeypatch.setattr(ew, "_safe_load_json", lambda _p: {})
    kept = ew._get_round_preserved_fields(17, state)
    for key in ("actualResults", "accuracy", "telemetryData", "gpReport"):
        assert kept[key] == state[key]
    state.pop("actualResults")
    state.pop("accuracy")
    tracker = {"rounds": {"17": {"actual": {"VER": {"position": 1}}}},
               "accuracy": {"17": {"accuracy_pct": 50}}}
    monkeypatch.setattr(ew, "_safe_load_json", lambda _p: tracker)
    kept = ew._get_round_preserved_fields(17, state)
    assert kept["actualResults"] == {"VER": 1}
    assert kept["accuracy"] == {"accuracy_pct": 50}


@pytest.mark.parametrize("field,value", [
    ("gpKey", "United States"), ("name", "United States Grand Prix"),
    ("date", "2026-10-25"), ("circuit", "Circuit of the Americas"),
    ("round", None),
])
def test_committed_qualifying_override_rejects_other_or_missing_event(tmp_path, monkeypatch, field, value):
    monkeypatch.setenv("F1_REGISTRY_ENABLED", os.getenv("F1_REGISTRY_ENABLED", "1"))
    import regenerate_post_quali as regen
    state = json.loads((DATA / "rounds/round_17.json").read_text())
    for session in state["weekendResults"]["sessions"]:
        if session["key"] == "qualifying":
            for row in session["rows"]:
                row["q3"] = row["time"]
    state[field] = value
    (tmp_path / "round_17.json").write_text(json.dumps(state))
    monkeypatch.setattr(fpu, "set_qualifying_override", lambda *_a, **_k: pytest.fail("wrong event injected"))
    assert not regen.inject_committed_qualifying(17, 2026, str(tmp_path))


def test_committed_qualifying_override_accepts_verified_same_event(tmp_path, monkeypatch):
    monkeypatch.setenv("F1_REGISTRY_ENABLED", os.getenv("F1_REGISTRY_ENABLED", "1"))
    import regenerate_post_quali as regen
    (tmp_path / "round_17.json").write_text((DATA / "rounds/round_17.json").read_text())
    injected = []
    monkeypatch.setattr(fpu, "set_qualifying_override", lambda *a, **k: injected.append((a, k)))
    assert regen.inject_committed_qualifying(17, 2026, str(tmp_path))
    assert injected[0][0][0:2] == (2026, "Singapore")
    assert injected[0][0][2]["RUS"] > 0


@pytest.mark.parametrize("wrong_identity", [False, True])
def test_committed_qualifying_override_rejects_pending_or_contradictory_session(tmp_path, monkeypatch, wrong_identity):
    monkeypatch.setenv("F1_REGISTRY_ENABLED", os.getenv("F1_REGISTRY_ENABLED", "1"))
    import regenerate_post_quali as regen
    state = json.loads((DATA / "rounds/round_17.json").read_text())
    session = next(s for s in state["weekendResults"]["sessions"] if s["key"] == "qualifying")
    if wrong_identity:
        session["eventIdentity"] = {"season": 2026, "round": 17, "name": "Singapore Grand Prix",
                                    "date": "2026-10-11", "circuitId": "americas"}
    else:
        session["status"] = "pending"
    (tmp_path / "round_17.json").write_text(json.dumps(state))
    monkeypatch.setattr(fpu, "set_qualifying_override", lambda *_a, **_k: pytest.fail("unverified session injected"))
    assert not regen.inject_committed_qualifying(17, 2026, str(tmp_path))


@pytest.mark.parametrize("field,value", [
    ("RoundNumber", None), ("EventName", "United States Grand Prix"),
    ("EventDate", "2026-10-25"), ("Location", "Austin"),
])
def test_replay_rejects_same_round_other_or_missing_event_before_telemetry(monkeypatch, field, value):
    from types import SimpleNamespace
    import export_race_replay as replay
    event = {"RoundNumber": 17, "EventName": "Singapore Grand Prix",
             "EventDate": "2026-10-11", "Location": "Marina Bay"}
    event[field] = value
    session = SimpleNamespace(event=event, load=lambda **_k: pytest.fail("wrong event telemetry loaded"))
    monkeypatch.setattr(replay.fastf1, "get_session", lambda *_a: session)
    with pytest.raises(SystemExit, match="wrong-event guard"):
        replay.build_replay(17, 2026, "Singapore", 1.0)


def test_replay_verified_identity_still_loads_requested_telemetry(monkeypatch):
    from types import SimpleNamespace
    import export_race_replay as replay
    calls = []
    session = SimpleNamespace(event={"RoundNumber": 17, "EventName": "Singapore Grand Prix",
                                    "EventDate": "2026-10-11", "Location": "Marina Bay"},
                              load=lambda **k: calls.append(k), laps=None)
    monkeypatch.setattr(replay.fastf1, "get_session", lambda *_a: session)
    with pytest.raises(SystemExit, match="no laps"):
        replay.build_replay(17, 2026, "Singapore", 1.0)
    assert calls == [{"laps": True, "telemetry": True, "weather": False, "messages": False}]


@pytest.mark.parametrize("phase", ["preview", "post-quali"])
def test_automatic_export_honors_durable_publication_hold(tmp_path, monkeypatch, phase):
    path = tmp_path / "round_17.json"
    original = (DATA / "rounds/round_17.json").read_text()
    path.write_text(original)
    monkeypatch.setattr(ew, "ROUNDS_DIR", str(tmp_path))
    monkeypatch.setattr(ew, "_ensure_dirs", lambda: pytest.fail("held forecast reached the pipeline"))
    with pytest.raises(ValueError, match="publication hold"):
        ew.export_round_data(17, prediction_phase=phase)
    assert path.read_text() == original


@pytest.mark.parametrize("wrong_venue", [False, True])
def test_historical_layout_fallback_requires_verified_provider_identity(monkeypatch, wrong_venue):
    from types import SimpleNamespace
    import generate_circuit_svg as geometry
    import pandas as pd
    expected = {8: {**CALENDAR[17], "date": "2025-10-05", "fastf1_date": "2025-10-05"}}
    monkeypatch.setattr(geometry, "_verified_session_calendar", lambda year, _gp: expected if year == 2025 else {})
    event = {"RoundNumber": 8, "EventName": "Singapore Grand Prix", "EventDate": "2025-10-05",
             "Location": "Austin" if wrong_venue else "Marina Bay"}
    loads = []
    tel = pd.DataFrame({"X": range(100), "Y": range(100)})
    session = SimpleNamespace(event=event, load=lambda **k: loads.append(k),
                              laps=SimpleNamespace(pick_fastest=lambda: SimpleNamespace(get_telemetry=lambda: tel)),
                              get_circuit_info=lambda: "verified-layout")
    monkeypatch.setattr(geometry.fastf1, "get_session", lambda *_a: session)
    result = geometry._load_telemetry(2026, "Singapore")
    if wrong_venue:
        assert result is None and not loads
    else:
        assert result[0] is tel and result[1] == "verified-layout" and len(loads) == 1


def test_preserved_forecasts_never_become_pre_sepang_predictions():
    archive = ROOT / "archive/event-identity-2026-10-11"
    raw = (archive / "originals.json.gz").read_bytes()
    manifest = json.loads((archive / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["archiveSha256"]
    assert hashlib.sha256((archive / "original-assets.tar.gz").read_bytes()).hexdigest() == manifest["assetsArchiveSha256"]
    originals = json.loads(gzip.decompress(raw))
    for path, stored in originals.items():
        assert hashlib.sha256(stored["content"].encode()).hexdigest() == stored["sha256"], path
    for rnd in range(16, 23):
        assert not (ROOT / f"models/registry/2026_round_{rnd:02d}").exists()
    for rnd in range(17, 23):
        assert f"models/registry/2026_round_{rnd:02d}/metadata.json" in originals
    for rnd in range(18, 24):
        current = json.loads((DATA / f"rounds/round_{rnd:02}.json").read_text())
        old = json.loads(originals[f"website/public/data/rounds/round_{rnd-1:02}.json"]["content"])
        assert current["classification"] == old["classification"]
        assert current["generatedAt"] == old["generatedAt"]
        assert current["gpKey"] == old["gpKey"]
    singapore = json.loads((DATA / "rounds/round_17.json").read_text())
    sepang = json.loads((DATA / "rounds/round_16.json").read_text())
    assert not singapore.get("actualResults") and not singapore["classification"]
    assert not sepang["classification"] and "accuracy" not in sepang
    assert singapore["publicationHold"]["originalForecast"]["generatedAt"] == "2026-10-10T10:22:59Z"
    assert "16" not in json.loads((ROOT / "predicted_results_2026.json").read_text())
    report = json.loads((DATA / "gp_accuracy_report.json").read_text())
    assert report["overallAccuracy"]["roundsWithActual"] == 15
    assert all(r["round"] < 16 for r in report["gpReports"])
    history = json.loads((DATA / "circuit_history.json").read_text())
    assert all(w["season"] < 2026 for w in history["Singapore"]["pastWinners"])
    assert history["Bahrain"]["poleToWinPct"] is None
    season = json.loads((DATA / "season.json").read_text())
    assert season["totalRounds"] == 23
    assert len(season["completedRounds"]) == 16
    assert 16 not in season["forecastRounds"] and 17 not in season["forecastRounds"]
    assert len(season["forecastRounds"]) == 21
    assert all(jolpica_matches(RACES[r], 2026, r, CALENDAR) for r in season["completedRounds"])
