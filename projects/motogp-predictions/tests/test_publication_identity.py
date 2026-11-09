"""Wrong-event regression: an unclassified GP must not renumber later events."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from motogp_predictions import build_snapshot, config, export, forward_eval, publication


class HoldContract(BaseModel):
    schemaVersion: Literal[1]
    sport: Literal["MotoGP"]
    season: int
    status: Literal["held"]
    reasonCode: str
    message: str
    issues: list[dict] = Field(min_length=1)
    sourceSnapshot: str
    snapshotSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    references: list[str]
    recovery: str
    routes: dict[str, list]


def event(key, date, country):
    return {"id": key, "short_name": key.upper(), "sponsored_name": key,
            "date_start": date, "date_end": date, "country": {"iso": country},
            "circuit": {"name": key + " circuit", "place": key}}


class FixtureApi:
    def __init__(self, *, cancelled=True):
        self.full = [event("first", "2026-01-01", "TH"), event("aus", "2026-10-25", "AU"),
                     event("mal", "2026-11-01", "MY"), event("qat", "2026-11-08", "QA")]
        self.finished = list(reversed(copy.deepcopy(self.full)))
        self.cancelled = cancelled

    def season_uuid(self, year):
        return "season-uuid"

    def premier_category_uuid(self, season):
        return "category-uuid"

    def events(self, season, *, finished_only=True):
        return copy.deepcopy(self.finished if finished_only else self.full)

    def sessions(self, event_id, category):
        types = ["SPR", "Q1", "Q2"] if self.cancelled and event_id == "aus" else ["RAC", "SPR", "Q1", "Q2"]
        return [{"id": f"{event_id}:{kind}", "type": kind[0] if kind.startswith("Q") else kind,
                 "number": int(kind[1]) if kind.startswith("Q") else None} for kind in types]

    def classification(self, session):
        key = session.split(":")[0]
        return [{"rider": {"id": key, "full_name": key + " Rider", "number": 1},
                 "position": 1, "points": 25, "constructor": {"name": "Ducati"}}]


def build(api):
    return build_snapshot.build_season(api, 2026, lambda rider: rider.upper())


def test_missing_race_preserves_full_calendar_uuid_slots():
    api = FixtureApi()
    original = copy.deepcopy(api.full)
    snapshot = build(api)
    assert [e["eventId"] for e in snapshot["fullCalendar"]] == ["first", "aus", "mal", "qat"]
    assert snapshot["completedRounds"] == [1, 3, 4]
    assert [(e["round"], e["eventId"]) for e in snapshot["calendar"]] == [(1, "first"), (3, "mal"), (4, "qat")]
    assert set(snapshot["results"]) == {"1", "3", "4"}
    assert set(snapshot["qualifying"]) == {"1", "3", "4"}
    assert snapshot["results"]["3"]["feature"][0]["code"] == "MAL"
    assert snapshot["results"]["4"]["feature"][0]["code"] == "QAT"
    assert api.full == original
    # The ingester can retain truthful IDs, but count-based consumers must not
    # publish them until explicit sparse-coverage support exists.
    assert [e["code"] for e in publication.snapshot_issues(snapshot)] == ["unsupported-completed-round-gap"]


def test_contiguous_verified_control_remains_publishable():
    assert publication.snapshot_issues(build(FixtureApi(cancelled=False))) == []


def test_sparse_corrected_ids_cannot_reach_count_based_forecasting(tmp_path, monkeypatch):
    snapshot = build(FixtureApi())
    (tmp_path / "official_2026.json").write_text(json.dumps(snapshot))
    monkeypatch.setattr(config, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "_SNAP", snapshot)
    monkeypatch.setattr(export.model, "forecast_round", lambda *a, **k: pytest.fail("sparse input reached the model"))
    monkeypatch.setattr(forward_eval, "evaluate_season", lambda *a, **k: pytest.fail("sparse input was evaluated"))
    public = tmp_path / "published"
    path = export.write(public)
    assert json.loads(path.read_text())["issues"][0]["code"] == "unsupported-completed-round-gap"
    assert forward_eval.write(public, 2026) == 0
    assert not (public / "motogp.json").exists()


def test_refresh_in_the_same_process_cannot_publish_with_stale_configuration(tmp_path, monkeypatch):
    snapshot = build(FixtureApi(cancelled=False))
    stale = copy.deepcopy(snapshot)
    stale["riders"] = []
    raw = json.dumps(snapshot).encode()
    (tmp_path / "official_2026.json").write_bytes(raw)
    monkeypatch.setattr(config, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "_SNAP", stale)
    decision = publication.current_hold()
    assert [issue["code"] for issue in decision["issues"]] == ["loaded-snapshot-changed"]
    assert decision["snapshotSha256"] == hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(config, "_SNAP", snapshot)
    assert publication.current_hold() is None


@pytest.mark.parametrize("kind", ["duplicate_full", "missing_id", "unknown_finished", "duplicate_finished", "wrong_venue"])
def test_ambiguous_uuid_or_conflicting_identity_is_rejected(kind):
    api = FixtureApi()
    if kind == "duplicate_full":
        api.full[1]["id"] = api.full[0]["id"]
    elif kind == "missing_id":
        api.full[0].pop("id")
    elif kind == "unknown_finished":
        api.finished[0]["id"] = "not-on-calendar"
    elif kind == "duplicate_finished":
        api.finished.append(copy.deepcopy(api.finished[0]))
    else:
        api.finished[0]["circuit"]["name"] = "wrong circuit"
    with pytest.raises(ValueError):
        build(api)


def shifted_snapshot():
    snapshot = build(FixtureApi())
    # Reproduce the old independent completed-race numbering exactly.
    snapshot["completedRounds"] = [1, 2, 3]
    for i, e in enumerate(snapshot["calendar"], start=1):
        e["round"] = i
    for key in ("results", "qualifying"):
        values = snapshot[key]
        snapshot[key] = {str(i): value for i, value in enumerate(values.values(), start=1)}
    return snapshot


def test_shift_is_reported_with_recorded_and_scheduled_event_evidence():
    issues = publication.snapshot_issues(shifted_snapshot())
    assert [(e["round"], e["recorded"]["shortName"], e["scheduled"]["shortName"],
             e["matchingScheduledRounds"]) for e in issues] == [(2, "MAL", "AUS", [3]), (3, "QAT", "MAL", [4])]


@pytest.mark.parametrize("kind", ["duplicate", "boolean", "missing_result", "wrong_season", "malformed"])
def test_malformed_inputs_cannot_clear_a_hold(tmp_path, monkeypatch, kind):
    snapshot = build(FixtureApi(cancelled=False))
    if kind == "duplicate":
        snapshot["completedRounds"].append(1)
    elif kind == "boolean":
        snapshot["calendar"][0]["round"] = True
    elif kind == "missing_result":
        snapshot["results"].pop("2")
    elif kind == "wrong_season":
        snapshot["season"] = 2025
    else:
        snapshot["fullCalendar"] = "unreadable"
    monkeypatch.setattr(config, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "_SNAP", snapshot)
    (tmp_path / "official_2026.json").write_text(json.dumps(snapshot))
    decision = publication.current_hold()
    assert decision["status"] == "held"
    assert decision["snapshotSha256"] == hashlib.sha256((tmp_path / "official_2026.json").read_bytes()).hexdigest()


def test_hold_prunes_public_claims_preserves_private_input_and_is_idempotent(tmp_path, monkeypatch):
    raw_dir, public = tmp_path / "private", tmp_path / "public"
    raw_dir.mkdir()
    snapshot = shifted_snapshot()
    raw = json.dumps(snapshot).encode()
    source = raw_dir / "official_2026.json"
    source.write_bytes(raw)
    monkeypatch.setattr(config, "_DATA_DIR", raw_dir)
    monkeypatch.setattr(config, "_SNAP", snapshot)
    for folder in ("rounds", "probabilities", "forward_eval", "historical_backtest", "reliability_plots"):
        (public / folder).mkdir(parents=True)
        (public / folder / "stale.json").write_text('{"misleading":true}')
    for name in ("motogp.json", "calibration_summary.json", "model_health.json", "evidence.json",
                 "promotion_status.json", "seasons.json", publication.EXPORT_RECEIPT):
        (public / name).write_text('{"misleading":true}')
    (public / "notes.txt").write_text("preserve unrelated work")
    monkeypatch.setattr(export.model, "forecast_round", lambda *a, **k: pytest.fail("held export ran the model"))
    monkeypatch.setattr(forward_eval, "evaluate_season", lambda *a, **k: pytest.fail("held export scored results"))
    status = export.write(public)
    assert status.name == publication.STATUS_FILE
    before = status.read_bytes()
    HoldContract.model_validate(json.loads(before))
    assert json.loads(before)["snapshotSha256"] == hashlib.sha256(raw).hexdigest()
    assert list(public.glob("*.json")) == [status]
    assert not any(p.is_dir() for p in public.iterdir())
    assert forward_eval.write(public, 2026) == 0
    assert status.read_bytes() == before
    assert source.read_bytes() == raw
    assert (public / "notes.txt").read_text() == "preserve unrelated work"


def test_current_published_corpus_matches_the_source_decision():
    data = Path(__file__).resolve().parents[1] / "website/public/data"
    expected = publication.current_hold()
    if expected is None:
        assert not (data / publication.STATUS_FILE).exists()
        return
    actual = json.loads((data / publication.STATUS_FILE).read_text())
    HoldContract.model_validate(actual)
    assert actual == expected
    assert not any((data / d).exists() for d in ("rounds", "probabilities", "forward_eval"))
    assert not any((data / f).exists() for f in ("motogp.json", "evidence.json", "model_health.json", "calibration_summary.json"))
