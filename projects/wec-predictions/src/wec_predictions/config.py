"""FIA WEC configuration — derived from the committed Al Kamel snapshots.

Endurance differs from every single-seat series in this suite on one axis that
shapes the whole model: it is **multi-class**. A round is not one race for one
field — it is Hypercar, LMP2 and LMGT3 (plus the GTE classes in older seasons)
running together but scored separately. So the competitor is the **car entry**
(``<CLASS_TAG>-<number>``, e.g. ``HYP-15``), the model forecasts each class as
its own field, and everything downstream (markets, standings, the site) is keyed
by class.

Like MotoGP this project carries **no hand-authored roster or pace table**: every
entry, team, manufacturer and result is read from the committed snapshots that
:mod:`wec_predictions.build_snapshot` pulls from the official timing archive
(``data/official_<season>.json`` current, ``data/history/<year>.json`` corpus).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Team

SPORT = "FIA WEC"

_DEFAULT_SEASON = 2026
_DATA_DIR = Path(os.environ.get("WEC_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
# Prior seasons that make up the offline training corpus (leakage-safe).
HISTORY_SEASONS = (2021, 2022, 2023, 2024, 2025)


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("WEC_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


@lru_cache(maxsize=16)
def load_snapshot(year: int) -> dict:
    for path in (_DATA_DIR / f"official_{year}.json", _DATA_DIR / "history" / f"{year}.json"):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


_SNAP = load_snapshot(SEASON)

# --------------------------------------------------------------------------- #
# Classes — the fields we forecast, in display priority. Each gets a chart hue.
# --------------------------------------------------------------------------- #
CLASSES: list[str] = list(_SNAP.get("classes") or ["HYPERCAR", "LMGT3"])

CLASS_COLORS = {
    "HYPERCAR": "#3DDC97",   # WEC endurance green (top class)
    "LMP1": "#3DDC97",
    "LMP2": "#4EA8DE",       # prototype blue
    "LMGT3": "#F4A259",      # GT amber
    "LMGTE PRO": "#F4A259",
    "LMGTE AM": "#E76F51",   # GT-Am terracotta
    "GTE": "#F4A259",
}
CLASS_LABEL = {
    "HYPERCAR": "Hypercar", "LMP1": "LMP1", "LMP2": "LMP2", "LMGT3": "LMGT3",
    "LMGTE PRO": "LMGTE Pro", "LMGTE AM": "LMGTE Am", "GTE": "GTE",
}


def class_color(cls: str) -> str:
    return CLASS_COLORS.get(cls, "#8A8A8A")


def class_label(cls: str) -> str:
    return CLASS_LABEL.get(cls, cls.title())


# --------------------------------------------------------------------------- #
# Entries (this season's cars) + fast lookups.
# --------------------------------------------------------------------------- #
_ENTRIES: list[dict] = _SNAP.get("entries") or []
ENTRIES: list[dict] = _ENTRIES

TEAM_OF: dict[str, str] = {e["code"]: e.get("team") or "?" for e in _ENTRIES}
MANUF_OF: dict[str, str] = {e["code"]: e.get("manufacturer") or "?" for e in _ENTRIES}
CLASS_OF: dict[str, str] = {e["code"]: e.get("class") or "?" for e in _ENTRIES}
ENTRY_NUMBER: dict[str, str] = {e["code"]: e.get("number") or "" for e in _ENTRIES}
ENTRY_META: dict[str, dict] = {e["code"]: e for e in _ENTRIES}


def entries_in_class(cls: str) -> list[dict]:
    return [e for e in _ENTRIES if e.get("class") == cls]


# Manufacturers as pseudo-teams for the palette (charts/badges).
_MANUF_COLORS = {
    "Ferrari": "#DA291C", "Toyota": "#EB0A1E", "Porsche": "#B9975B", "Cadillac": "#941E32",
    "BMW": "#0166B1", "Peugeot": "#0A122A", "Alpine": "#005BA9", "Aston Martin": "#00665E",
    "Genesis": "#171C21", "Lamborghini": "#B4A46A", "McLaren": "#FF8000", "Lexus": "#1A1A1A",
    "Corvette": "#C5B358", "Ford": "#00274D", "Mercedes-AMG": "#00A19B", "Oreca": "#5B6670",
}
MANUFACTURERS: list[str] = list(_SNAP.get("manufacturers") or [])
TEAMS: list[Team] = [Team(name=m, color=_MANUF_COLORS.get(m, "#8A8A8A")) for m in MANUFACTURERS]

# --------------------------------------------------------------------------- #
# Calendar.
# --------------------------------------------------------------------------- #
FULL_CALENDAR: list[dict] = _SNAP.get("fullCalendar") or []
COMPLETED_ROUNDS_LIST: list[int] = list(_SNAP.get("completedRounds") or [])
COMPLETED_ROUNDS = len(COMPLETED_ROUNDS_LIST)
TOTAL_ROUNDS = _SNAP.get("totalRounds") or len(FULL_CALENDAR)

# --------------------------------------------------------------------------- #
# Points — standard WEC per-class top-10 table (used for the standings view and
# the standings baseline; the model ranks on positions, which are rule-agnostic).
# --------------------------------------------------------------------------- #
FEATURE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

# --------------------------------------------------------------------------- #
# Model knobs (see model.py). Tuned by walk-forward validation (forward_eval /
# the never-ship-worse gate) across the 2024-2026 three-class era.
# --------------------------------------------------------------------------- #
PACE_BASE = 100.0
PACE_SPREAD = 0.55

# Endurance skill blend — an ENSEMBLE tuned by walk-forward validation (see
# forward_eval / the never-ship-worse gate). Two facts drive it:
#   * WEC is dominated by a stable set of works entries, so **recent results**
#     (the last race, this-season form) are a very strong predictor — hard to
#     beat with anything fancier.
#   * But a single race is noisy, so a **smoothed cross-season entry rating**
#     (Elo, which carries a car's strength year to year — HYP-7 is Toyota #7
#     across seasons) plus the **team's** operational quality de-noise it.
# Blending recency with the smoothed rating beats each naive baseline (last-race
# order and season-form order) on win- and podium-Brier across 2021-2026; leaning
# only on form/last-race, or only on Elo, is worse in one regime or the other.
SKILL_WEIGHTS = {"last": 1.0, "elo": 0.8, "history": 0.4, "team": 0.3}

# Plackett-Luce temperature. Endurance is high-variance (mechanical attrition,
# multi-hour strategy), so a slightly hotter default than the sprint series.
BASE_TEMPERATURE = 0.60
DEFAULT_SAMPLES = 6000

ROOKIE_RACE_THRESHOLD = 2
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4


def next_round() -> int:
    """The first not-yet-completed round (what we forecast)."""
    done = set(COMPLETED_ROUNDS_LIST)
    for r in range(1, (TOTAL_ROUNDS or 0) + 1):
        if r not in done:
            return r
    return (max(done) + 1) if done else 1


def round_meta(round: int) -> dict:
    for e in FULL_CALENDAR:
        if int(e.get("round", -1)) == round:
            return e
    return {"round": round, "place": f"Round {round}", "country": "", "event": f"Round {round}"}
