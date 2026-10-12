"""Synthetic safety cases for an offline model; no provider/network/training job."""
from datetime import datetime, timezone
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest

import ridge_shadow as shadow
from tests.publication_inputs import repair_input


def _event(season=2026, rnd=3, venue="Singapore"):
    return {"season": season, "round": rnd, "rows": [
        {"season": season, "round": rnd, "driver": "AAA", "team": "Team A", "venue": venue,
         "field_size": 2, "grid_fraction": 0.5, "quali_fraction": 1, "quali_gap": 0.01,
         "penalty_delta": -0.5, "actual_position": 1, "stored_position": 1},
        {"season": season, "round": rnd, "driver": "BBB", "team": "Team A", "venue": venue,
         "field_size": 2, "grid_fraction": 1, "quali_fraction": 0.5, "quali_gap": 0,
         "penalty_delta": 0.5, "actual_position": 2, "stored_position": 2},
    ]}


def _history():
    return pd.DataFrame([
        {"season": 2025, "round": 18, "driver": "AAA", "team": None, "venue": "Singapore", "finish_fraction": 0.1},
        {"season": 2026, "round": 1, "driver": "AAA", "team": "Team A", "venue": "Australia", "finish_fraction": 0.2},
        {"season": 2026, "round": 1, "driver": "BBB", "team": "Team A", "venue": "Australia", "finish_fraction": 0.4},
        {"season": 2026, "round": 3, "driver": "AAA", "team": "Team A", "venue": "Singapore", "finish_fraction": 1.0},
        {"season": 2026, "round": 4, "driver": "AAA", "team": "Team A", "venue": "Singapore", "finish_fraction": 1.0},
    ])


def test_current_and_future_outcomes_cannot_change_target_features():
    event, history = _event(), _history()
    before = shadow.features_for_event(event, history)
    future = (history.season > 2026) | ((history.season == 2026) & (history["round"] >= 3))
    history.loc[future, "finish_fraction"] = 100
    after = shadow.features_for_event(event, history)
    pd.testing.assert_frame_equal(before, after)
    row = before.set_index("driver").loc["AAA"]
    assert row.driver_recent_mean == pytest.approx(0.15)
    assert row.driver_track_mean == pytest.approx(0.1)
    assert row.team_recent_mean == pytest.approx(0.3)
    assert row.team_recent_n == 1  # no backwards assignment of the unknown historical team


def test_relocated_venue_keeps_history_missing():
    frame = shadow.features_for_event(_event(venue="Sepang"), _history())
    assert frame.driver_track_n.eq(0).all()
    assert frame.driver_track_mean.isna().all()
    assert shadow._venue("Bahrain", 2026, 16) == "Sepang"
    assert shadow._venue("Bahrain", 2025, 4) == "Bahrain"


def test_scaling_and_missing_value_encoding_fit_only_training_rows():
    train = pd.DataFrame({"grid_fraction": [0.5, 1.0], "actual_position": [1, 2], "field_size": [2, 2]})
    model = shadow.fit_fold(train, shadow.GRID_FEATURES)
    scaler = model.steps[1][1]
    assert scaler.mean_[0] == pytest.approx(0.75)
    model.predict(pd.DataFrame({"grid_fraction": [1000.0]}))
    assert scaler.mean_[0] == pytest.approx(0.75)


@pytest.mark.parametrize("destination", ["website/public/data/rounds/r.json", "predicted_results_2026.json", "models/registry/r/model.json"])
def test_shadow_writer_cannot_touch_served_or_feature_state(tmp_path, destination):
    path = tmp_path / destination
    with pytest.raises(ValueError, match="serving/feature state"):
        shadow.write_artifact(path, {"candidate": True}, root=tmp_path)
    assert not list(tmp_path.rglob("*"))


def test_artifact_is_complete_and_cannot_be_overwritten(tmp_path):
    path = tmp_path / "reports/ridge-shadow/candidate.json"
    shadow.write_artifact(path, {"status": "evaluation"}, root=tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        shadow.write_artifact(path, {"status": "replacement"}, root=tmp_path)
    assert path.read_bytes() == before
    assert json.loads(before)["status"] == "evaluation"
    assert list(path.parent.iterdir()) == [path]


def test_invalid_artifact_is_rejected_before_any_write(tmp_path):
    with pytest.raises(ValueError):
        shadow.write_artifact(tmp_path / "reports/ridge-shadow/bad.json", {"score": np.nan}, root=tmp_path)
    assert not list(tmp_path.rglob("*"))


@pytest.mark.parametrize("reason", ["started", "partial-outcome", "future-source"])
def test_candidate_rejects_cutoff_violations_before_fit(reason, monkeypatch):
    event = _event()
    for row in event["rows"]:
        row["actual_position"] = None
    event.update(raceStartUtc="2026-10-11T12:00:00Z", coverage={"actualRows": 0,
                 "qualifyingSourceCheckedAt": "2026-10-11T05:15:33Z", "gridSourceCheckedAt": "2026-10-11T05:15:33Z"})
    now = datetime(2026, 10, 11, 6, tzinfo=timezone.utc)
    if reason == "started":
        now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    elif reason == "partial-outcome":
        event["coverage"]["actualRows"] = 1
    else:
        event["coverage"]["gridSourceCheckedAt"] = "2026-10-11T07:00:00Z"
    monkeypatch.setattr(shadow, "fit_fold", lambda *_a: pytest.fail("invalid candidate reached model fit"))
    with pytest.raises(ValueError):
        shadow.candidate(event, [], pd.DataFrame(), {}, now=now)


def test_chronological_folds_keep_all_drivers_of_target_event_out():
    events = [_event(rnd=r) for r in (3, 1, 2)]
    for event in events:
        event.update(labelled=True, name="Synthetic event")
    report = shadow.evaluate(events, _history(), min_train_events=1)
    assert [row["round"] for row in report["rounds"]] == [2, 3]
    assert report["rounds"][0]["trainEvents"] == [[2026, 1]]
    assert report["rounds"][0]["trainRows"] == 2
    assert report["rounds"][1]["trainEvents"] == [[2026, 1], [2026, 2]]
    assert report["rounds"][1]["trainRows"] == 4


def test_generation_that_finishes_after_race_returns_no_candidate(tmp_path, monkeypatch):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    cutoff = clock["now"]
    clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="finished outside"):
        value = shadow.candidate(target, events, history, audit, now=cutoff)
        shadow.write_artifact(tmp_path / "reports/ridge-shadow/candidate.json", value, root=tmp_path)
    assert not (tmp_path / "reports").exists()


def _isolated_snapshot(tmp_path, monkeypatch, *, future_fetched=False):
    """Load the exact saved pre-race inputs; never touch served data."""
    original = shadow.PROJECT_ROOT
    for relative in ("data/history.duckdb", "website/public/data/season.json",
                     "website/public/data/rounds/round_17.json"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = original / relative if relative == "data/history.duckdb" else repair_input(relative)
        shutil.copy2(source, destination)
    if future_fetched:
        path = tmp_path / "website/public/data/rounds/round_17.json"
        state = json.loads(path.read_bytes())
        for session in state["weekendResults"]["sessions"]:
            if session["key"] in ("qualifying", "startingGrid"):
                session["fetchedAt"] = "2026-10-11T11:59:59Z"
        path.write_text(json.dumps(state))
    monkeypatch.setattr(shadow.subprocess, "check_output", lambda *_a, **_k: "isolated-test\n")
    events, history, audit = shadow.load_inputs(tmp_path)
    target = next(e for e in events if e["round"] == 17)
    prior = _event(rnd=2)
    prior.update(labelled=True)
    clock = {"now": datetime(2026, 10, 11, 11, 59, 58, tzinfo=timezone.utc)}
    class ControlledDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]
    monkeypatch.setattr(shadow, "datetime", ControlledDateTime)
    monkeypatch.setattr(shadow, "PROJECT_ROOT", tmp_path)
    return target, [prior], history, audit, clock


def _mutate_source(root, kind):
    if kind == "database":
        path = root / "data/history.duckdb"
        path.write_bytes(path.read_bytes() + b"changed snapshot")
    else:
        path = root / "website/public/data/rounds/round_17.json"
        value = json.loads(path.read_bytes())
        value["actualResults" if kind == "outcome" else "generatedAt"] = {"VER": 1} if kind == "outcome" else "changed snapshot"
        path.write_text(json.dumps(value))


@pytest.mark.parametrize("mutation", ["json", "database", "outcome"])
def test_sources_changed_after_load_are_rejected_before_candidate_fit(tmp_path, monkeypatch, mutation):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    _mutate_source(tmp_path, mutation)
    monkeypatch.setattr(shadow, "fit_fold", lambda *_a: pytest.fail("changed source reached fit"))
    with pytest.raises(ValueError, match="source snapshot"):
        shadow.candidate(target, events, history, audit, now=clock["now"])
    assert not (tmp_path / "reports").exists()


def test_outcome_added_during_provenance_rejects_candidate(tmp_path, monkeypatch):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    original = shadow.digest
    def changing_digest(value):
        _mutate_source(tmp_path, "outcome")
        return original(value)
    monkeypatch.setattr(shadow, "digest", changing_digest)
    with pytest.raises(ValueError, match="source snapshot"):
        shadow.candidate(target, events, history, audit, now=clock["now"])


def test_deadline_reached_during_provenance_rejects_candidate(tmp_path, monkeypatch):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    original = shadow.digest
    def late_digest(value):
        clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        return original(value)
    monkeypatch.setattr(shadow, "digest", late_digest)
    with pytest.raises(ValueError, match="pre-race"):
        shadow.candidate(target, events, history, audit, now=clock["now"])


@pytest.mark.parametrize("boundary", ["before-write", "during-stage", "during-link", "source-during-stage"])
def test_sealing_rechecks_deadline_and_sources_leaving_no_artifact(tmp_path, monkeypatch, boundary):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    value = shadow.candidate(target, events, history, audit, now=clock["now"])
    path = tmp_path / "reports/ridge-shadow/candidate.json"
    if boundary == "before-write":
        clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    elif boundary in ("during-stage", "source-during-stage"):
        original = shadow.os.fsync
        def changed_stage(fd):
            original(fd)
            if boundary == "source-during-stage":
                _mutate_source(tmp_path, "outcome")
            else:
                clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        monkeypatch.setattr(shadow.os, "fsync", changed_stage)
    else:
        original = shadow.os.link
        def late_link(source, destination):
            original(source, destination)
            clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        monkeypatch.setattr(shadow.os, "link", late_link)
    with pytest.raises(ValueError, match="source snapshot|pre-race"):
        shadow.write_artifact(path, value, root=tmp_path)
    assert not path.exists()
    assert not path.parent.exists() or not list(path.parent.iterdir())


def test_verified_candidate_seals_with_unchanged_sources_and_cannot_overwrite(tmp_path, monkeypatch):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    value = shadow.candidate(target, events, history, audit, now=clock["now"])
    path = tmp_path / "reports/ridge-shadow/candidate.json"
    shadow.write_artifact(path, value, root=tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        shadow.write_artifact(path, value, root=tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("module", shadow.IMPLEMENTATION_FILES)
def test_dependency_mutated_after_capture_rejects_without_artifact(tmp_path, monkeypatch, module):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch)
    copied = tmp_path / "implementation"
    for source in shadow.IMPLEMENTATION_MANIFEST:
        path = copied / source["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shadow.IMPLEMENTATION_ROOT / source["path"], path)
    monkeypatch.setattr(shadow, "IMPLEMENTATION_ROOT", copied)
    value = shadow.candidate(target, events, history, audit, now=clock["now"])
    path = copied / module
    path.write_bytes(path.read_bytes() + b"\n# changed after capture\n")
    with pytest.raises(ValueError, match="implementation snapshot"):
        shadow.write_artifact(tmp_path / "reports/ridge-shadow/candidate.json", value, root=tmp_path)
    assert not (tmp_path / "reports").exists()


def test_old_verified_time_cannot_hide_future_fetched_time(tmp_path, monkeypatch):
    target, events, history, audit, clock = _isolated_snapshot(tmp_path, monkeypatch, future_fetched=True)
    assert target["coverage"]["qualifyingSourceCheckedAt"] == "2026-10-11T05:15:33Z"
    monkeypatch.setattr(shadow, "fit_fold", lambda *_a: pytest.fail("future source reached fit"))
    with pytest.raises(ValueError, match="every source timestamp"):
        shadow.candidate(target, events, history, audit, now=clock["now"])


def test_provenance_records_exact_modules_versions_and_dirty_hashes(tmp_path, monkeypatch):
    _target, _events, _history, audit, _clock = _isolated_snapshot(tmp_path, monkeypatch)
    implementation = audit["implementation"]
    assert [f["path"] for f in implementation["files"]] == list(shadow.IMPLEMENTATION_FILES)
    assert implementation["manifestSha256"] == shadow.digest(shadow.IMPLEMENTATION_MANIFEST)
    assert implementation["runtimeVersions"] == shadow.RUNTIME_VERSIONS
    assert set(implementation["runtimeVersions"]) == {"python", "duckdb", "numpy", "pandas", "scipy", "scikit-learn"}
    assert not implementation["allFilesMatchSourceCommit"]  # isolated commit deliberately has different bytes
    assert all(f["sha256"] and f["commitSha256"] and not f["matchesSourceCommit"] for f in implementation["files"])
