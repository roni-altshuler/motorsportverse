"""Snapshot IndyCar source — the PRIMARY source of truth for this project.

IndyCar has no public results API, so the committed, human-verified history
files (``data/history_<year>.json``, curated from Wikipedia and verified
against the official standings — ``data/CURATION_REPORT.md``) are not a cache:
they ARE the canonical data. ``data/history_<SEASON>.json`` doubles as the
active-season snapshot; :mod:`indycar_predictions.refresh` appends newly
completed rounds to that one file behind strict validation, so there is a
single source per season for the model, the backtests and the website export.

Serves the classified order for curated rounds and returns ``None`` for
rounds/seasons it has no data for, so the composite falls through to the
synthetic generator. This makes the default pipeline real *and*
offline/deterministic — no network at build or test time.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Result

from .. import config

SOURCE_NAME = "snapshot"

# snapshot.py lives in src/indycar_predictions/sources/, so the project root
# (which holds data/) is three parents up.
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"

#: Time / gap / lapped statuses in the curated data mean the car was RUNNING
#: at the flag: "1:52:21.6997", "+0.0233", "+1 Lap", "-2 Laps", "−1 Lap"
#: (unicode minus). Anything wordy (Contact, Mechanical, Crash T3, Did Not
#: Start, Disqualified, ...) is a retirement/non-finish for the hazard head.
_RUNNING_STATUS = re.compile(r"^\s*[+\-−]?\s*\d[\d:.,]*(\s*Laps?)?\s*$", re.IGNORECASE)


def is_dnf_status(status: str | None) -> bool:
    """IndyCar classifies every car; a non-running status is a retirement."""
    if status is None:
        return False  # grid-backed old rounds record no status for finishers
    s = re.sub(r"</?nowiki>", "", str(status)).strip()
    if not s:
        return False
    return not _RUNNING_STATUS.match(s)


def snapshot_row(result: dict) -> dict:
    """One curated result dict → the snapshot-shaped row the model consumes."""
    name = result.get("driver") or ""
    status = result.get("status")
    return {
        "position": result.get("position"),
        "code": config.driver_code(name),
        "name": name,
        "team": result.get("team") or "",
        "engine": result.get("engine") or "",
        "grid": result.get("grid"),
        "laps": result.get("laps"),
        "status": status,
        "dnf": is_dnf_status(status),
        "points": result.get("points"),
    }


def _snapshot_path(year: int) -> Path:
    # The env-overridable config data dir wins (test seam), then the default.
    base = config._DATA_DIR if config._DATA_DIR.exists() else _DATA_DIR
    return base / f"history_{year}.json"


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
    """Parsed history file for a season (cached). ``{}`` when absent.

    ``year`` 0 (default) means the active season — the family call shape.
    """
    if path:
        return _load(path)
    return _load(str(_snapshot_path(year or config.SEASON)))


class SnapshotIndycarSource:
    name = SOURCE_NAME

    def __init__(self, path: str | None = None):
        # ``path`` pins the ACTIVE season's snapshot (test seam); other years
        # still resolve through the per-season history files.
        self._active_path = path

    def _snap(self, year: int) -> dict:
        if year == config.SEASON and self._active_path:
            return _load(self._active_path)
        return load_snapshot(year)

    def _round(self, year: int, round: int) -> dict | None:
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return None
        for rd in snap.get("rounds", []):
            if int(rd.get("round", 0)) == round:
                return rd
        return None

    # ------------------------------------------------------------------ #
    def results(self, year: int, round: int, race_index: int = 0) -> list[Result] | None:
        rd = self._round(year, round)
        if rd is None:
            return None
        rows = [snapshot_row(r) for r in rd.get("results", [])]
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
                status=r.get("status") or ("Running" if not r["dnf"] else "Retired"),
                points=r.get("points"),
            )
            for r in classified
        ]

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full snapshot rows (every classified car incl. retirees, with grid/
        status/points/laps) — the entry list with attrition flags."""
        rd = self._round(year, round)
        if rd is None:
            return None
        rows = [snapshot_row(r) for r in rd.get("results", [])]
        rows.sort(key=lambda r: (r["position"] is None, r["position"] or 0))
        return rows

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first), or None.

        For a COMPLETED round the curated ``grid`` fields carry the real
        starting grid; for the UPCOMING round :mod:`..refresh` may store a
        pre-race order under the snapshot's optional ``qualifying`` block
        (``{round: [driver names]}``) — the post-quali seam.
        """
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return None
        pre = (snap.get("qualifying") or {}).get(str(round))
        if pre:
            return [config.driver_code(n) for n in pre]
        rd = self._round(year, round)
        if rd is None:
            return None
        gridded = [
            (int(r["grid"]), config.driver_code(r.get("driver") or ""))
            for r in rd.get("results", [])
            if r.get("grid")
        ]
        if len(gridded) < 3:
            return None
        return [code for _, code in sorted(gridded)]

    def completed_rounds(self, year: int) -> list[int]:
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return []
        return sorted(int(rd.get("round", 0)) for rd in snap.get("rounds", []))

    def calendar(self, year: int) -> list[dict]:
        """Calendar entries for a season, built from the curated rounds.

        The ACTIVE season's full calendar (incl. future rounds) comes from
        ``config.CALENDAR_META``; archive seasons expose the rounds they ran.
        """
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return []
        out = []
        for rd in snap.get("rounds", []):
            tt = rd.get("track_type") or "road"
            out.append(
                {
                    "round": int(rd.get("round", 0)),
                    "key": rd.get("venue_key") or f"round-{rd.get('round')}",
                    "venue": rd.get("venue") or f"Round {rd.get('round')}",
                    "raceName": rd.get("name") or "",
                    "date": rd.get("date") or "",
                    "trackType": tt,
                    "kind": "oval" if tt == "oval" else ("street" if tt == "street" else "circuit"),
                    "completed": True,
                }
            )
        return out

    def standings(self, year: int) -> list[dict]:
        """The curated official standings (points AS AWARDED, verified)."""
        snap = self._snap(year)
        if not snap or year != snap.get("season"):
            return []
        return [
            {
                "position": int(s["pos"]),
                "code": config.driver_code(s.get("driver") or ""),
                "name": s.get("driver") or "",
                "points": float(s.get("points") or 0.0),
            }
            for s in snap.get("final_standings", [])
        ]
