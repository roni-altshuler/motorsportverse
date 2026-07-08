"""Snapshot FE source — real results from the committed offline snapshots.

Reads ``data/official_<SEASON>.json`` (produced by
:mod:`formula_e_predictions.refresh` from the Pulselive API) for the active
season, and ``data/seasons/<year>.json`` (produced by
:mod:`formula_e_predictions.backfill`) for archived seasons. Serves the
**real** classified order for completed rounds and returns ``None`` for rounds
it has no data for, so the composite falls through to the synthetic generator.
This makes the default pipeline real *and* offline/deterministic — no network
at build or test time.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "snapshot"

# snapshot.py lives in src/formula_e_predictions/sources/, so the project root
# (which holds data/) is three parents up.
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _snapshot_path(year: int) -> Path:
    # The env-overridable config data dir wins (test seam), then the default.
    base = config._DATA_DIR if config._DATA_DIR.exists() else _DATA_DIR
    if year == config.SEASON:
        return base / f"official_{year}.json"
    return base / "seasons" / f"{year}.json"


@lru_cache(maxsize=32)
def _load(path_str: str) -> dict:
    p = Path(path_str)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_snapshot(year: int = 0, path: str | None = None) -> dict:
    """Parsed snapshot dict for a season (cached). ``{}`` when absent.

    ``year`` 0 (default) means the active season — the F3-parity call shape.
    """
    if path:
        return _load(path)
    return _load(str(_snapshot_path(year or config.SEASON)))


class SnapshotFESource:
    name = SOURCE_NAME

    def __init__(self, path: str | None = None):
        # ``path`` pins the ACTIVE season's snapshot (test seam); other years
        # still resolve through the season directory.
        self._active_path = path

    def _snap(self, year: int) -> dict:
        if year == config.SEASON and self._active_path:
            return _load(self._active_path)
        return load_snapshot(year)

    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 0) -> list[Result] | None:
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return None
        block = snap.get("results", {}).get(str(round))
        if not block:
            return None
        rows = block.get("race") or []
        classified = sorted(
            (r for r in rows if r.get("position")), key=lambda r: r["position"]
        )
        if not classified:
            return None
        return [
            Result(
                competitor=r["code"],
                position=int(r["position"]),
                grid=r.get("grid"),
                status=r.get("status", "Finished"),
                points=r.get("points"),
            )
            for r in classified
        ]

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full snapshot rows (classified + DNFs) — the entry list with flags."""
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return None
        block = snap.get("results", {}).get(str(round))
        return list(block.get("race") or []) if block else None

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first) captured in the snapshot, or None.

        ``refresh`` stores the combined-qualifying classification under
        ``snapshot["qualifying"][str(round)]`` — including the *upcoming* round
        once its session has run but before the race, driving the post-quali
        forecast.
        """
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return None
        order = snap.get("qualifying", {}).get(str(round))
        return list(order) if order else None

    def completed_rounds(self, year: int) -> list[int]:
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return []
        return [c["round"] for c in snap.get("calendar", []) if c.get("completed")]

    def calendar(self, year: int) -> list[dict]:
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return []
        return list(snap.get("calendar", []))
