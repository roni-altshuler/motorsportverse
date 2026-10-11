"""Calendar insertions must not turn a valid round echo into a wrong-event grade."""
import copy
import gzip
import hashlib
import io
import json
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
