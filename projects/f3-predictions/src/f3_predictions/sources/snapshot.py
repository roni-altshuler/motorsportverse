"""Snapshot F3 source — real results from the committed offline snapshot.

Reads ``data/official_2026.json`` (produced by :mod:`f3_predictions.refresh`
from fiaformula3.com) and serves the **real** classified order for completed
rounds. Returns ``None`` for rounds not in the snapshot so the composite falls
through to the synthetic generator for upcoming rounds. This makes the default
pipeline real *and* offline/deterministic — no network at build or test time.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Result

SOURCE_NAME = "snapshot"

# snapshot.py lives in src/f3_predictions/sources/, so the project root (which
# holds data/) is three parents up.
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_DEFAULT_PATH = _DATA_DIR / "official_2026.json"

# race_index → snapshot session key (matches FIA: 0 = sprint, 1 = feature).
_SESSION_KEY = {0: "sprint", 1: "feature"}


@lru_cache(maxsize=4)
def load_snapshot(path: str | None = None) -> dict:
    """Parsed snapshot dict (cached). Returns {} if the file is absent."""
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


class SnapshotF3Source:
    name = SOURCE_NAME

    def __init__(self, path: str | None = None):
        self._snap = load_snapshot(path)

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        if not self._snap or year != self._snap.get("season"):
            return None
        block = self._snap.get("results", {}).get(str(round))
        if not block:
            return None
        rows = block.get(_SESSION_KEY.get(race_index, "feature")) or []
        classified = sorted(
            (r for r in rows if r.get("position")), key=lambda r: r["position"]
        )
        if not classified:
            return None
        return [
            Result(
                competitor=r["code"],
                position=int(r["position"]),
                grid=None,
                status=r.get("status", "Finished"),
                points=None,
            )
            for r in classified
        ]

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first) captured in the snapshot, or ``None``.

        ``refresh`` stores the scraped qualifying classification under
        ``snapshot["qualifying"][str(round)]`` — including the *upcoming* round
        once its Friday session has run but before the race. Returns ``None`` when
        absent so the composite falls through to the live feed / predicted grid.
        """
        if not self._snap or year != self._snap.get("season"):
            return None
        order = self._snap.get("qualifying", {}).get(str(round))
        return list(order) if order else None

    def completed_rounds(self, year: int) -> list[int]:
        if not self._snap or year != self._snap.get("season"):
            return []
        return [c["round"] for c in self._snap.get("calendar", []) if c.get("completed")]
