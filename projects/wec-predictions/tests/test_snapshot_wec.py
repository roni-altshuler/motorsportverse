"""The committed FIA WEC snapshots parse and carry the multi-class shape the model
and export read: classes, per-round per-class results, and car-entry metadata.

These are the offline source of truth (``data/official_<season>.json`` +
``data/history/<year>.json``); downstream builds never touch the network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _snapshot_paths() -> list[Path]:
    paths = sorted(_DATA_DIR.glob("official_*.json")) + sorted((_DATA_DIR / "history").glob("*.json"))
    return paths


def test_snapshots_exist():
    paths = _snapshot_paths()
    assert paths, "no committed WEC snapshots found under data/"
    # the current season + the historical corpus should both be present
    assert (_DATA_DIR / "official_2026.json").exists()
    assert list((_DATA_DIR / "history").glob("*.json")), "no history corpus committed"


@pytest.mark.parametrize("path", _snapshot_paths(), ids=lambda p: p.name)
def test_snapshot_parses_and_has_multiclass_shape(path):
    snap = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(snap, dict)
    assert snap.get("sport") == "FIA WEC"
    assert isinstance(snap["season"], int)

    classes = snap.get("classes")
    assert isinstance(classes, list) and classes, f"{path.name}: no classes"

    # results keyed by round → class → list of entry rows
    results = snap.get("results")
    assert isinstance(results, dict) and results, f"{path.name}: no results"
    for rnd_key, block in results.items():
        assert rnd_key.isdigit(), f"{path.name}: non-numeric round key {rnd_key!r}"
        assert isinstance(block, dict) and block
        for cls, rows in block.items():
            assert cls in classes, f"{path.name}: round {rnd_key} class {cls} not in classes"
            assert isinstance(rows, list) and rows
            for row in rows:
                assert "code" in row and "number" in row
                assert "position" in row and "status" in row


@pytest.mark.parametrize("path", _snapshot_paths(), ids=lambda p: p.name)
def test_entries_carry_car_identity(path):
    snap = json.loads(path.read_text(encoding="utf-8"))
    entries = snap.get("entries")
    assert isinstance(entries, list) and entries, f"{path.name}: no entries"
    for e in entries:
        assert {"code", "number", "class", "team", "manufacturer"} <= set(e), (
            f"{path.name}: entry missing identity fields: {e.get('code')}"
        )
        assert e["class"] in snap["classes"]
        # competitor code is <CLASS_TAG>-<number>
        assert "-" in e["code"]


def test_completed_rounds_are_consistent():
    snap = json.loads((_DATA_DIR / "official_2026.json").read_text(encoding="utf-8"))
    completed = snap.get("completedRounds") or []
    assert completed, "no completed rounds in the committed 2026 snapshot"
    for rnd in completed:
        assert str(rnd) in snap["results"], f"completed round {rnd} has no results block"
