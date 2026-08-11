"""The committed IMSA snapshots parse and carry the multi-class shape the model
and export read: classes, per-round per-class results, and car-entry metadata.

These are the offline source of truth (``data/official_<season>.json`` +
``data/history/<year>.json``); downstream builds never touch the network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_SPORT = "IMSA WeatherTech SportsCar Championship"


def _snapshot_paths() -> list[Path]:
    paths = sorted(_DATA_DIR.glob("official_*.json")) + sorted((_DATA_DIR / "history").glob("*.json"))
    return paths


def test_snapshots_exist():
    paths = _snapshot_paths()
    assert paths, "no committed IMSA snapshots found under data/"
    # the current season + the historical corpus should both be present
    assert (_DATA_DIR / "official_2026.json").exists()
    assert list((_DATA_DIR / "history").glob("*.json")), "no history corpus committed"


@pytest.mark.parametrize("path", _snapshot_paths(), ids=lambda p: p.name)
def test_snapshot_parses_and_has_multiclass_shape(path):
    snap = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(snap, dict)
    assert snap.get("sport") == _SPORT
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
def test_round_numbers_are_sequential(path):
    """IMSA event folders interleave support series, so build_snapshot renumbers to
    a clean 1..N. Verify the completed rounds are exactly that dense sequence."""
    snap = json.loads(path.read_text(encoding="utf-8"))
    completed = snap.get("completedRounds") or []
    assert completed, f"{path.name}: no completed rounds"
    assert completed == list(range(1, len(completed) + 1)), (
        f"{path.name}: completed rounds not a dense 1..N sequence: {completed}"
    )


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


def test_known_winner_2025_rolex24_gtp():
    """Spot-check a known result: the 2025 Rolex 24 (round 1, Daytona) GTP winner is
    the #7 Porsche Penske 963 → competitor code GTP-7."""
    hist = _DATA_DIR / "history" / "2025.json"
    if not hist.exists():
        pytest.skip("2025 history snapshot not committed")
    snap = json.loads(hist.read_text(encoding="utf-8"))
    gtp_r1 = snap["results"]["1"].get("GTP")
    assert gtp_r1, "no GTP block for 2025 round 1"
    winner = min((r for r in gtp_r1 if r.get("position")), key=lambda r: r["position"])
    assert winner["code"] == "GTP-7", f"expected GTP-7, got {winner['code']}"
