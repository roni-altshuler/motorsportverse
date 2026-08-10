"""Snapshot MotoGP source — real results from the committed snapshots.

Serves the **real** classified order for any season the project has committed
(``data/official_<season>.json`` + ``data/history/<year>.json``). Because
MotoGP's results feed covers every completed round, there is no synthetic
fallback for scored races — a round either has real results (it has run) or
returns ``None`` (not yet run), which the composite reads as "not completed".

``race_index`` follows the golden-template convention: 0 = the Saturday **Sprint**,
1 = the Sunday **Grand Prix** (the "feature").
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "snapshot"
_SESSION_KEY = {0: "sprint", 1: "feature"}


class SnapshotMotoGPSource:
    name = SOURCE_NAME

    def _snap(self, year: int) -> dict:
        return config.load_snapshot(year)

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result] | None:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return None
        block = snap.get("results", {}).get(str(round))
        if not block:
            return None
        rows = block.get(_SESSION_KEY.get(race_index, "feature")) or []
        classified = sorted((r for r in rows if r.get("position")), key=lambda r: r["position"])
        if not classified:
            return None
        # grid comes from that round's qualifying order (index+1); None if absent.
        grid_order = snap.get("qualifying", {}).get(str(round)) or []
        grid_pos = {c: i + 1 for i, c in enumerate(grid_order)}
        return [
            Result(
                competitor=r["code"],
                position=int(r["position"]),
                grid=grid_pos.get(r["code"]),
                status=r.get("status") or "Finished",
                points=float(r["points"]) if r.get("points") is not None else None,
            )
            for r in classified
        ]

    def qualifying(self, year: int, round: int) -> list[str] | None:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return None
        order = snap.get("qualifying", {}).get(str(round))
        return list(order) if order else None

    def completed_rounds(self, year: int) -> list[int]:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return []
        return list(snap.get("completedRounds") or [])

    def provenance(self, year: int, round: int, race_index: int = 1) -> str:
        return SOURCE_NAME
