"""A release fixture is explicitly synthetic; no model is trained or promoted."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd
import pytest

import f1_prediction_utils as fpu
import publication_review as review

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 11, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def release_inputs(monkeypatch):
    state = json.loads((ROOT / "website/public/data/rounds/round_17.json").read_text())
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz or timezone.utc)
    monkeypatch.setattr(review, "datetime", FixedDateTime)
    monkeypatch.setattr(review, "model_code_sha256", lambda: "a" * 64)
    audit = {"sourceSnapshotSha256": review._digest(review.official_input_snapshot(state)),
             "modelCodeSha256": "a" * 64, "reviewNote": "Synthetic reviewed release fixture",
             "reviewedAt": "2026-10-11T05:45:00Z"}
    return state, audit


def _generated_inputs(release):
    snapshot = release["snapshot"]
    times = {row["driver"]: fpu._parse_laptime_to_seconds(row["time"])
             for row in snapshot["qualifying"]["rows"] if fpu._parse_laptime_to_seconds(row["time"]) is not None}
    grid = {row["driver"]: row["position"] for row in snapshot["startingGrid"]["rows"]}
    merged = pd.DataFrame({"Driver": list(grid), "QualifyingRank": list(grid.values())})
    return times, grid, merged


def test_explicit_release_validates_new_inputs_and_separates_withdrawn_claim(release_inputs):
    state, audit = release_inputs
    original = copy.deepcopy(state)
    release = review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=NOW)
    review.validate_generated_inputs(release, *_generated_inputs(release))
    provenance = review.release_provenance(release, "2026-10-11T05:55:00Z", {"synthetic": True}, now=NOW)
    assert provenance["withdrawnForecast"]["generatedAt"] == "2026-10-10T10:22:59Z"
    assert provenance["generatedAt"] == "2026-10-11T05:55:00Z"
    assert provenance["modelCodeSha256"] == "a" * 64
    assert provenance["modelConfigSha256"] == review._digest({"synthetic": True})
    assert state == original


@pytest.mark.parametrize("field,value", [
    ("sourceSnapshotSha256", "wrong-input-snapshot"), ("modelCodeSha256", "unaudited-model"),
    ("reviewNote", ""), ("reviewedAt", "2026-10-10T10:00:00Z"),
    ("reviewedAt", "2026-10-11T05:20:00Z"),
    ("reviewedAt", "2026-10-11T07:00:00Z"),
])
def test_release_rejects_changed_or_unaudited_inputs(release_inputs, field, value):
    state, audit = release_inputs
    audit[field] = value
    with pytest.raises(ValueError, match="publication hold"):
        review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=NOW)


@pytest.mark.parametrize("mutation", ["wrong-event", "pending-grid", "different-source-event", "grid-after-review"])
def test_release_rejects_unverified_official_input_state(release_inputs, mutation):
    state, audit = release_inputs
    grid_session = next(s for s in state["weekendResults"]["sessions"] if s["key"] == "startingGrid")
    if mutation == "wrong-event":
        state["circuit"] = "Circuit of the Americas"
    elif mutation == "pending-grid":
        grid_session["status"] = "pending"
    elif mutation == "different-source-event":
        grid_session["sourceUrl"] = "https://www.formula1.com/en/results/2026/races/1308/bahrain/starting-grid"
    else:
        grid_session["fetchedAt"] = "2026-10-11T05:50:00Z"
    audit["sourceSnapshotSha256"] = review._digest(review.official_input_snapshot(state))
    with pytest.raises(ValueError, match="publication hold"):
        review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=NOW)


@pytest.mark.parametrize("mutation", ["wrong-times", "invalid-time", "quali-grid", "model-ignores-penalty", "partial-field"])
def test_release_checks_actual_model_inputs_including_russell_penalty(release_inputs, mutation):
    state, audit = release_inputs
    release = review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=NOW)
    times, grid, merged = _generated_inputs(release)
    if mutation == "wrong-times":
        times["VER"] += 1
    elif mutation == "invalid-time":
        times["VER"] = float("nan")
    elif mutation == "quali-grid":
        grid["RUS"] = 6
    elif mutation == "model-ignores-penalty":
        merged.loc[merged.Driver == "RUS", "QualifyingRank"] = 6
    else:
        merged = merged.iloc[:-1]
    with pytest.raises(ValueError, match="publication hold"):
        review.validate_generated_inputs(release, times, grid, merged)


def test_release_must_finish_before_race_and_cannot_reuse_original_timestamp(release_inputs):
    state, audit = release_inputs
    after_start = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="after race start"):
        review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=after_start)
    release = review.prepare_reviewed_release(state, 17, fpu.CALENDAR, audit, now=NOW)
    with pytest.raises(ValueError, match="pre-race window"):
        review.release_provenance(release, "2026-10-10T10:22:59Z", {}, now=NOW)
    with pytest.raises(ValueError, match="pre-race window"):
        review.release_provenance(release, "2026-10-11T05:55:00Z", {}, now=after_start)


@pytest.mark.parametrize("approved", [False, True])
def test_export_requires_explicit_valid_review_before_entering_generation(tmp_path, monkeypatch, release_inputs, approved):
    import export_website_data as exporter
    state, audit = release_inputs
    path = tmp_path / "round_17.json"
    path.write_text(json.dumps(state))
    original = path.read_bytes()
    monkeypatch.setattr(exporter, "ROUNDS_DIR", str(tmp_path))
    class GenerationReached(Exception):
        pass
    def generation():
        raise GenerationReached("reviewed generation reached")
    monkeypatch.setattr(exporter, "_ensure_dirs", generation)
    if not approved:
        audit["sourceSnapshotSha256"] = "changed-input"
    with pytest.raises(GenerationReached if approved else ValueError,
                       match="reviewed generation reached" if approved else "publication hold"):
        exporter.export_round_data(17, prediction_phase="post-quali", publication_release=audit)
    assert path.read_bytes() == original
