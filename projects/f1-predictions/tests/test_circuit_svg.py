"""Circuit-geometry generation must never blank a good map on a telemetry miss.

Regression guard: the circuit SVG comes from FastF1 *telemetry*, which is
unreachable from CI runners. When a fetch fails, ``generate_circuit_svg`` must
KEEP any previously-derived geometry (it is immutable per circuit) instead of
overwriting it with null — otherwise every re-exported round's track map blanks.
"""
from __future__ import annotations

import json

import generate_circuit_svg as gcs


def _seed_round(tmp_path, monkeypatch, *, with_geometry: bool):
    rounds = tmp_path / "rounds"
    rounds.mkdir()
    monkeypatch.setattr(gcs, "ROUNDS_DIR", rounds)
    monkeypatch.setattr(gcs, "SEASON_JSON", tmp_path / "season.json")
    (tmp_path / "season.json").write_text(
        json.dumps({"season": 2026, "calendar": [{"round": 10, "gpKey": "Belgium"}]})
    )
    circuit_info = {"type": "permanent", "laps": 44}
    if with_geometry:
        circuit_info["geometry"] = {
            "viewBox": "0 0 1000 1000",
            "path": "M100,100 L200,200 L300,150",
            "corners": [{"number": 1, "x": 100, "y": 100, "name": None}],
            "source": "fastf1",
        }
    (rounds / "round_10.json").write_text(json.dumps({"round": 10, "circuitInfo": circuit_info}))
    return rounds / "round_10.json"


class TestCircuitGeometryPreservation:
    def test_failed_fetch_keeps_existing_geometry(self, tmp_path, monkeypatch):
        path = _seed_round(tmp_path, monkeypatch, with_geometry=True)
        # Telemetry unreachable → build_geometry returns None. force=True so we
        # bypass the "already present" short-circuit and reach the failure path.
        monkeypatch.setattr(gcs, "build_geometry", lambda *a, **k: None)

        ok = gcs.process_round(10, None, force=True)

        geo = json.loads(path.read_text())["circuitInfo"]["geometry"]
        assert ok is True
        assert isinstance(geo, dict) and geo.get("path")  # NOT wiped to null

    def test_cold_start_writes_null(self, tmp_path, monkeypatch):
        path = _seed_round(tmp_path, monkeypatch, with_geometry=False)
        monkeypatch.setattr(gcs, "build_geometry", lambda *a, **k: None)

        ok = gcs.process_round(10, None, force=True)

        geo = json.loads(path.read_text())["circuitInfo"]["geometry"]
        assert ok is False
        assert geo is None  # genuine cold start → null fallback in UI

    def test_successful_fetch_writes_geometry(self, tmp_path, monkeypatch):
        path = _seed_round(tmp_path, monkeypatch, with_geometry=False)
        fake = {"viewBox": "0 0 1000 1000", "path": "M0,0 L1,1", "corners": [], "source": "fastf1"}
        monkeypatch.setattr(gcs, "build_geometry", lambda *a, **k: fake)

        ok = gcs.process_round(10, None, force=True)

        geo = json.loads(path.read_text())["circuitInfo"]["geometry"]
        assert ok is True
        assert geo == fake
