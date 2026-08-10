"""Snapshot WRC source — real rally classifications from the committed snapshots.

Rally has one scored classification per round (stored under the ``"rally"`` key),
so there is no race_index. A round either has a real result (it has run) or
returns ``None`` (upcoming).
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "snapshot"


class SnapshotWrcSource:
    name = SOURCE_NAME

    def _snap(self, year: int) -> dict:
        return config.load_snapshot(year)

    def results(self, year: int, round: int) -> list[Result] | None:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return None
        block = snap.get("results", {}).get(str(round))
        if not block:
            return None
        rows = block.get("rally") or []
        classified = sorted((r for r in rows if r.get("position")), key=lambda r: r["position"])
        if not classified:
            return None
        return [
            Result(
                competitor=r["code"],
                position=int(r["position"]),
                grid=None,
                status=r.get("status") or "Finished",
                points=float(r["points"]) if r.get("points") is not None else None,
            )
            for r in classified
        ]

    def completed_rounds(self, year: int) -> list[int]:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return []
        return list(snap.get("completedRounds") or [])

    def provenance(self, year: int, round: int) -> str:
        return SOURCE_NAME
