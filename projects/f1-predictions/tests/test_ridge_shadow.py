"""Synthetic safety cases for an offline model; no provider/network/training job."""
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
import pytest

import ridge_shadow as shadow


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
    shadow.write_artifact(path, {"status": "shadow_only"}, root=tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        shadow.write_artifact(path, {"status": "replacement"}, root=tmp_path)
    assert path.read_bytes() == before
    assert json.loads(before)["status"] == "shadow_only"
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
    class LateDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(shadow, "datetime", LateDateTime)
    target, prior = _event(rnd=3), _event(rnd=2)
    for row in target["rows"]:
        row["actual_position"] = None
    prior.update(labelled=True)
    target.update(raceStartUtc="2026-10-11T12:00:00Z", coverage={"actualRows": 0,
                  "qualifyingSourceCheckedAt": "2026-10-11T05:15:33Z", "gridSourceCheckedAt": "2026-10-11T05:15:33Z",
                  "qualifyingSourceUrl": "https://www.formula1.com/en/results/2026/races/1296/singapore/qualifying",
                  "gridSourceUrl": "https://www.formula1.com/en/results/2026/races/1296/singapore/starting-grid"})
    with pytest.raises(ValueError, match="finished outside"):
        value = shadow.candidate(target, [prior], _history(), {},
                                 now=datetime(2026, 10, 11, 6, tzinfo=timezone.utc))
        shadow.write_artifact(tmp_path / "reports/ridge-shadow/candidate.json", value, root=tmp_path)
    assert not list(tmp_path.rglob("*"))
