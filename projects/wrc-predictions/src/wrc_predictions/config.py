"""WRC configuration — derived from the committed real-data snapshots.

Like the MotoGP project (and unlike the spec series), WRC carries no hand-authored
roster or pace table: every crew, manufacturer, rally, surface and standings figure
comes from the committed snapshots that :mod:`wrc_predictions.build_snapshot` pulls
from the official wrc.com results API (``data/official_<season>.json`` +
``data/history/<year>.json``). This module is the thin WRC-domain layer on top.

What makes WRC *not* a circuit series:
* **One scored classification per round.** A rally is a single result (no sprint,
  no qualifying grid), so a round is one venue, one finishing order.
* **The surface defines the discipline.** Gravel, tarmac and snow are almost
  different sports; a snow specialist is not a Safari specialist. Every round
  carries its surface (from the snapshot) and the model blends a per-driver
  same-surface form signal — the genuine rally novelty.
* **Rich cross-season history.** Crews carry form across years, so the model seeds
  its driver/manufacturer Elo from prior seasons, not just this one.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Team, Venue, VenueKind

SPORT = "WRC"

_DEFAULT_SEASON = 2026
_DATA_DIR = Path(os.environ.get("WRC_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
HISTORY_SEASONS = (2021, 2022, 2023, 2024, 2025)

# Surface accent colours (chart/badge coding for the defining rally variable).
SURFACE_COLORS = {"gravel": "#B8722C", "tarmac": "#5B6670", "snow": "#7FB2D9"}


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("WRC_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        return int(json.loads((_DATA_DIR / "active_season.json").read_text())["season"])
    except Exception:
        return default


SEASON = _active_season()


@lru_cache(maxsize=8)
def load_snapshot(year: int) -> dict:
    for path in (_DATA_DIR / f"official_{year}.json", _DATA_DIR / "history" / f"{year}.json"):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


_SNAP = load_snapshot(SEASON)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "rally"


# Calendar (Venue.kind = stage for rally).
_CAL = _SNAP.get("calendar") or []
CALENDAR: list[Venue] = [
    Venue(key=_slug(e.get("name") or f"round-{e['round']}"),
          name=e.get("name") or f"Round {e['round']}",
          country=e.get("country"), kind=VenueKind.stage)
    for e in _CAL
]
CALENDAR_META: dict[int, dict] = {
    int(e["round"]): {"date": e.get("date") or "", "surface": e.get("surface") or "gravel",
                      "eventId": e.get("eventId")}
    for e in _CAL
}
SURFACE_OF: dict[int, str] = {r: m["surface"] for r, m in CALENDAR_META.items()}

COMPLETED_ROUNDS = len(_SNAP.get("completedRounds") or [])
TOTAL_ROUNDS = _SNAP.get("totalRounds") or len(CALENDAR)

# Manufacturers (top-tier constructors; driver.manufacturer may be a WRC2 make,
# which the model reads as a car-tier signal). Colours are brand-plausible.
_MAN_COLORS = {"Toyota": "#EB0A1E", "Hyundai": "#0B2C5F", "Ford": "#1B3E8C",
               "M-Sport Ford": "#1B3E8C", "Skoda": "#4BA82E", "Citroen": "#C8102E",
               "Lancia": "#003F87"}
MANUFACTURERS: list[str] = list(_SNAP.get("manufacturers") or _MAN_COLORS.keys())
TEAMS: list[Team] = [Team(name=m, color=_MAN_COLORS.get(m, "#8A8A8A")) for m in MANUFACTURERS]

_DRIVERS: list[dict] = _SNAP.get("drivers") or []
DRIVERS: list[dict[str, str]] = [
    {"code": d["code"], "name": d["name"], "team": d.get("manufacturer") or "Privateer"}
    for d in _DRIVERS
]
TEAM_OF: dict[str, str] = {d["code"]: (d.get("manufacturer") or "Privateer") for d in _DRIVERS}
DRIVER_NAME: dict[str, str] = {d["code"]: d["name"] for d in _DRIVERS}
DRIVER_NATION: dict[str, str | None] = {d["code"]: d.get("nationality") for d in _DRIVERS}

# WRC points (Rally1 base finishing points; the API's real season totals already
# include Super Sunday + Power Stage bonuses and drive the standings — this table
# only feeds the forward championship projection).
FEATURE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

# --------------------------------------------------------------------------- #
# Model knobs.
# --------------------------------------------------------------------------- #
PACE_BASE = 100.0
PACE_SPREAD = 0.55
# Skill blend: driver Elo dominates; the car (manufacturer/tier) matters a lot in
# rally (a Rally1 Toyota vs a WRC2 Skoda); same-surface form is the rally-specific
# signal (gravel/tarmac/snow specialists). Weights are relative, need not sum to 1.
SKILL_WEIGHTS = {"elo": 0.55, "history": 0.35, "team": 0.30, "surface": 0.35}
ROOKIE_RACE_THRESHOLD = 3
DEFAULT_SAMPLES = 4000
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4

# Championship-form ensemble. Rally has no qualifying grid, so current championship
# standing is a very strong predictor (in a dominated season it can beat a pure
# skill model outright). The production forecast therefore ENSEMBLES the skill
# model with a championship-form prior — validated (walk-forward 2023-2026) to beat
# the standings-order baseline on the live season (win 0.892 vs 0.893, podium 0.747
# vs 0.766) and on podium in every season, while the skill model still carries the
# surface/cross-season signal a bare standings heuristic can't. Weight = the skill
# model's share of the blend.
ENSEMBLE_MODEL_WEIGHT = 0.5
FORM_DECAY = 0.7  # geometric decay over the championship order for the form prior


def venue_for(round: int) -> Venue:
    idx = round - 1
    return CALENDAR[idx] if 0 <= idx < len(CALENDAR) else (
        CALENDAR[0] if CALENDAR else Venue(key="rally", name="Rally", kind=VenueKind.stage))


def surface_for_round(round: int) -> str:
    return SURFACE_OF.get(round, "gravel")


def next_round() -> int:
    return min(COMPLETED_ROUNDS + 1, len(CALENDAR)) if CALENDAR else 1
