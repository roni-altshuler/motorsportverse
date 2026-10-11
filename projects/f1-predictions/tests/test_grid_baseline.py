"""The baseline is its own immutable stream; every mutation uses temporary copies."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import pytest

import stage_grid_baseline as staging

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for relative in ("website/public/data/rounds/round_17.json", "website/public/data/season.json"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, path)
    sealed = ROOT / "website/public/data/baselines" / staging.ARTIFACT_FILE
    review = ROOT / "docs/qa/grid-baseline/source-verification.json"
    clock = {"now": datetime(2026, 10, 11, 7, 20, tzinfo=timezone.utc)}
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]
    monkeypatch.setattr(staging, "datetime", Clock)
    return tmp_path, sealed, review, clock


def test_stage_preserves_seal_and_model_hold_and_never_overwrites(isolated):
    root, sealed, review, _clock = isolated
    round_path = root / "website/public/data/rounds/round_17.json"
    original = round_path.read_bytes()
    receipt = staging.stage_grid_baseline(sealed, review, root)
    out = root / "website/public/data/baselines"
    assert (out / staging.ARTIFACT_FILE).read_bytes() == sealed.read_bytes()
    assert hashlib.sha256(sealed.read_bytes()).hexdigest() == receipt["artifactSha256"] == staging.SEALED_SHA256
    assert receipt["sealedAt"] == "2026-10-11T06:53:07.672909Z"
    assert receipt["forecastKind"] == "official_grid_baseline" and receipt["graded"] is False
    assert receipt["stagedAt"] == "2026-10-11T07:20:00Z"
    assert round_path.read_bytes() == original
    assert json.loads(original)["publicationHold"]["reason"] == "event-mismatch"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(FileExistsError):
        staging.stage_grid_baseline(sealed, review, root)
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}


@pytest.mark.parametrize("mutation", ["backdate", "learned-probability", "different-order"])
def test_changed_seal_rejected_without_display_record(isolated, mutation):
    root, sealed, review, _clock = isolated
    value = json.loads(sealed.read_bytes())
    if mutation == "backdate":
        value["generatedAt"] = "2026-10-10T06:00:00Z"
    elif mutation == "learned-probability":
        value["probabilities"] = {"VER": 0.9}
    else:
        value["classification"][0]["driver"] = "RUS"
    changed = root / "changed.json"
    changed.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="sealed baseline bytes"):
        staging.stage_grid_baseline(changed, review, root)
    assert not (root / "website/public/data/baselines").exists()


@pytest.mark.parametrize("condition", ["late", "stale-review", "future-review", "target-outcome", "changed-grid"])
def test_invalid_source_or_deadline_rejects_before_staging(isolated, condition):
    root, sealed, review, clock = isolated
    if condition == "late":
        clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    elif condition == "stale-review":
        clock["now"] = datetime(2026, 10, 11, 9, tzinfo=timezone.utc)
    elif condition == "future-review":
        clock["now"] = datetime(2026, 10, 11, 7, tzinfo=timezone.utc)
    else:
        path = root / "website/public/data/rounds/round_17.json"
        state = json.loads(path.read_bytes())
        if condition == "target-outcome":
            state["actualResults"] = {"VER": 1}
        else:
            grid = next(s for s in state["weekendResults"]["sessions"] if s["key"] == "startingGrid")
            grid["rows"][0]["position"] = 2
        path.write_text(json.dumps(state))
    with pytest.raises(ValueError):
        staging.stage_grid_baseline(sealed, review, root)
    assert not (root / "website/public/data/baselines").exists()


def test_deadline_crossed_during_link_leaves_no_baseline_record(isolated, monkeypatch):
    root, sealed, review, clock = isolated
    original = staging.os.link
    def late_link(source, destination):
        original(source, destination)
        clock["now"] = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(staging.os, "link", late_link)
    with pytest.raises(ValueError, match="pre-race"):
        staging.stage_grid_baseline(sealed, review, root)
    assert not list((root / "website/public/data/baselines").iterdir())
