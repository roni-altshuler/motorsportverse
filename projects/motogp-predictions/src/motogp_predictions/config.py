"""MotoGP configuration — derived from the committed real-data snapshots.

Unlike the spec-series projects (F3), MotoGP carries **no hand-authored roster or
latent-pace table**: every entrant, manufacturer, venue and standings figure is
read from the committed snapshots that :mod:`motogp_predictions.build_snapshot`
pulls from the official results API (``data/official_<season>.json`` for the
current season, ``data/history/<year>.json`` for the training corpus). This
module is the thin MotoGP-domain layer on top — points tables, manufacturer
identity/colours, and the model-tuning knobs that make MotoGP *not* F3:

* **The manufacturer matters.** MotoGP is not a spec series — a factory Ducati is
  a different weapon from a Yamaha — so the constructor weight is large here,
  the opposite of F3.
* **The sprint shares the grid.** MotoGP's Saturday Sprint starts from the *same*
  qualifying grid as Sunday's Grand Prix (no reverse grid); it is simply shorter
  and higher-variance. So both race heads read the real qualifying order.
* **Rich cross-season history.** Riders carry form across years, so the model
  seeds its rider/'manufacturer' Elo from prior seasons, not just this one.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Team, Venue, VenueKind

SPORT = "MotoGP"

_DEFAULT_SEASON = 2026
_DATA_DIR = Path(os.environ.get("MOTOGP_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
# Prior seasons that make up the offline training corpus (leakage-safe: the model
# only ever reads rounds strictly before the one it forecasts).
HISTORY_SEASONS = (2021, 2022, 2023, 2024, 2025)


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("MOTOGP_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


@lru_cache(maxsize=8)
def load_snapshot(year: int) -> dict:
    """Committed snapshot for a season ({} if absent)."""
    for path in (_DATA_DIR / f"official_{year}.json", _DATA_DIR / "history" / f"{year}.json"):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


_SNAP = load_snapshot(SEASON)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "venue"


# --------------------------------------------------------------------------- #
# Calendar — the full official season schedule (finished + upcoming).
# --------------------------------------------------------------------------- #
_FULL = _SNAP.get("fullCalendar") or _SNAP.get("calendar") or []
CALENDAR: list[Venue] = [
    Venue(
        key=_slug(e.get("venue") or e.get("shortName") or f"round-{e['round']}"),
        name=e.get("place") or e.get("venue") or e.get("name") or f"Round {e['round']}",
        country=e.get("country"),
        kind=VenueKind.circuit,
    )
    for e in _FULL
]
CALENDAR_META: dict[int, dict[str, str]] = {
    int(e["round"]): {
        "city": e.get("place") or "",
        "event": e.get("name") or "",
        "date": e.get("date") or "",
    }
    for e in _FULL
}

COMPLETED_ROUNDS = len(_SNAP.get("completedRounds") or [])
TOTAL_ROUNDS = _SNAP.get("totalRounds") or len(CALENDAR)

# --------------------------------------------------------------------------- #
# Manufacturers (the constructor-equivalent) + brand colours for charts/badges.
# Distinct, brand-plausible hues; unknown makes fall back to a neutral grey.
# --------------------------------------------------------------------------- #
_MANUFACTURER_COLORS = {
    "Ducati": "#C8102E",
    "Aprilia": "#22A6A0",
    "KTM": "#FF6900",
    "Yamaha": "#0A2472",
    "Honda": "#1C4E9C",
    "Suzuki": "#0F4C9A",
}
MANUFACTURERS: list[str] = list(_SNAP.get("manufacturers") or _MANUFACTURER_COLORS.keys())
TEAMS: list[Team] = [
    Team(name=m, color=_MANUFACTURER_COLORS.get(m, "#8A8A8A")) for m in MANUFACTURERS
]

# --------------------------------------------------------------------------- #
# Rider roster (this season's entrants) — code / name / manufacturer, all real.
# --------------------------------------------------------------------------- #
_RIDERS: list[dict] = _SNAP.get("riders") or []
RIDERS: list[dict[str, str]] = [
    {"code": r["code"], "name": r["name"], "team": r.get("manufacturer") or "?"}
    for r in _RIDERS
]
# Golden-template alias: the shared model/pipeline reads ``DRIVERS``.
DRIVERS = RIDERS

TEAM_OF: dict[str, str] = {r["code"]: (r.get("manufacturer") or "?") for r in _RIDERS}
DRIVER_NAME: dict[str, str] = {r["code"]: r["name"] for r in _RIDERS}
RIDER_NUMBER: dict[str, int | None] = {r["code"]: r.get("number") for r in _RIDERS}
RIDER_NATION: dict[str, str | None] = {r["code"]: r.get("nationality") for r in _RIDERS}

# --------------------------------------------------------------------------- #
# Points — MotoGP Grand Prix (top 15) and Saturday Sprint (top 9), 2023+ format.
# --------------------------------------------------------------------------- #
FEATURE_POINTS = {1: 25, 2: 20, 3: 16, 4: 13, 5: 11, 6: 10, 7: 9, 8: 8, 9: 7,
                  10: 6, 11: 5, 12: 4, 13: 3, 14: 2, 15: 1}
SPRINT_POINTS = {1: 12, 2: 9, 3: 7, 4: 6, 5: 5, 6: 4, 7: 3, 8: 2, 9: 1}

# --------------------------------------------------------------------------- #
# Model knobs — MotoGP-tuned (see model.py).
# --------------------------------------------------------------------------- #
PACE_BASE = 100.0          # neutral pace when there is no signal yet
PACE_SPREAD = 0.55         # pace units per unit of blended-skill z-score

# Skill blend. Unlike the F3 spec series, the **manufacturer/bike effect is large**
# in MotoGP, so ``team`` carries real weight. Rider signals still dominate (Márquez
# beats the bike) but the factory is a first-class term, not a rounding error.
SKILL_WEIGHTS = {"elo": 0.55, "history": 0.45, "team": 0.35, "ml": 0.5}

# The sprint starts from the SAME grid as the Grand Prix (no reverse grid) but is
# shorter → more variance and a slightly stronger track-position effect (harder to
# make up places over half the distance).
SPRINT_TEMPERATURE_BOOST = 0.15   # extra Plackett-Luce temperature on the sprint head
# Grid-position weight for the post-quali head. Tuned by walk-forward validation on
# 2026 R4-R12 (see forward_eval): at 0.18 the grid-conditioned forecast beats the
# raw-grid baseline on both win-Brier (0.816 vs 0.844) and podium-Brier (0.594 vs
# 0.748) while matching winner-hit — the honest "never ship worse than the grid"
# gate. Pre-quali (form-only) forecasts are weaker than the grid (qualifying is
# hugely predictive in MotoGP), so the post-quali forecast is the headline surface.
GRID_WEIGHT = 0.18                # pace cost per grid slot back (both heads, post-quali)

ROOKIE_RACE_THRESHOLD = 3
DEFAULT_SAMPLES = 4000

USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 2
ML_MIN_TRAIN_ROWS = 8
ML_MIN_SPLIT_ROWS = 12

# Honest calibration gate: probability calibration only turns on once enough real
# rounds have accrued. MotoGP ships with a full real corpus, so this is satisfied
# from round one — but the gate stays, matching every other series.
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4


def venue_for(round: int) -> Venue:
    idx = round - 1
    return CALENDAR[idx] if 0 <= idx < len(CALENDAR) else (CALENDAR[0] if CALENDAR else
        Venue(key="venue", name="Venue"))


def next_round() -> int:
    """The first not-yet-completed round (what we forecast)."""
    return min(COMPLETED_ROUNDS + 1, len(CALENDAR)) if CALENDAR else 1
