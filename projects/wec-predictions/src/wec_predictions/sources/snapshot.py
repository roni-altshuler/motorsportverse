"""Snapshot WEC source — real per-class results from the committed snapshots.

Serves the **real** within-class classified order for any season the project has
committed (``data/official_<season>.json`` + ``data/history/<year>.json``). A
round with no committed results returns ``None`` (not yet run). Everything is
keyed by ``cls`` (HYPERCAR / LMP2 / LMGT3 / …) because endurance is scored per
class.
"""
from __future__ import annotations

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "snapshot"


class SnapshotWecSource:
    name = SOURCE_NAME

    def _snap(self, year: int) -> dict:
        return config.load_snapshot(year)

    def classes(self, year: int) -> list[str]:
        return list(self._snap(year).get("classes") or [])

    def _round_block(self, year: int, round: int) -> dict:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return {}
        return snap.get("results", {}).get(str(round)) or {}

    def results(self, year: int, round: int, cls: str) -> list[Result] | None:
        """Within-class classified order (P1 first); None if the round has no data."""
        rows = self._round_block(year, round).get(cls)
        if not rows:
            return None
        classified = sorted((r for r in rows if r.get("position")), key=lambda r: r["position"])
        if not classified:
            return None
        return [
            Result(
                competitor=r["code"],
                position=int(r["position"]),
                grid=None,
                status=r.get("status") or "Classified",
                points=float(r["points"]) if r.get("points") is not None else None,
            )
            for r in classified
        ]

    def class_field(self, year: int, round: int, cls: str) -> list[str]:
        """Every entry code that started that class that round (classified + DNF)."""
        rows = self._round_block(year, round).get(cls) or []
        seen: list[str] = []
        for r in rows:
            if r["code"] not in seen:
                seen.append(r["code"])
        return seen

    def completed_rounds(self, year: int) -> list[int]:
        snap = self._snap(year)
        if not snap or snap.get("season") != year:
            return []
        return list(snap.get("completedRounds") or [])

    def provenance(self, year: int, round: int) -> str:
        return SOURCE_NAME
