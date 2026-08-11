"""IMSA WeatherTech SportsCar Championship configuration — from committed snapshots.

Like the FIA WEC, IMSA is **multi-class** endurance racing: a round is not one
race for one field, it is GTP (or DPi in the older era), LMP2, GTD PRO and GTD
running together but scored separately. So the competitor is the **car entry**
(``<CLASS_TAG>-<number>``, e.g. ``GTP-7`` is the Porsche Penske #7 across seasons),
the model forecasts each class as its own field, and everything downstream
(markets, standings, the site) is keyed by class.

Like MotoGP/WEC this project carries **no hand-authored roster or pace table**:
every entry, team, manufacturer and result is read from the committed snapshots
that :mod:`imsa_predictions.build_snapshot` pulls from the official Al Kamel timing
archive (``data/official_<season>.json`` current, ``data/history/<year>.json``
corpus).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from motorsport_data.schema import Team

SPORT = "IMSA WeatherTech SportsCar Championship"

_DEFAULT_SEASON = 2026
_DATA_DIR = Path(os.environ.get("IMSA_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
# Prior seasons that make up the offline training corpus (leakage-safe). The
# archive begins the modern era in 2022 (DPi), 2023 introduced GTP.
HISTORY_SEASONS = (2022, 2023, 2024, 2025)


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("IMSA_SEASON_YEAR", "").strip()
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
CLASSES: list[str] = list(_SNAP.get("classes") or ["GTP", "GTD"])

CLASS_COLORS = {
    "GTP": "#E10600",       # IMSA red — the top prototype class (2023+)
    "DPI": "#E10600",       # DPi — the top prototype class in the 2022 era
    "LMP2": "#4EA8DE",      # prototype blue
    "LMP3": "#3DDC97",      # prototype-lite green (2022-2023)
    "GTDPRO": "#F4A259",    # GT amber (pro crews)
    "GTD": "#B57BFF",       # GT purple (pro-am)
}
CLASS_LABEL = {
    "GTP": "GTP", "DPI": "DPi", "LMP2": "LMP2", "LMP3": "LMP3",
    "GTDPRO": "GTD PRO", "GTD": "GTD",
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
    "Porsche": "#B9975B", "Cadillac": "#941E32", "BMW": "#0166B1", "Acura": "#CE0E2D",
    "Ferrari": "#DA291C", "Aston Martin": "#00665E", "Mercedes-AMG": "#00A19B",
    "Lamborghini": "#B4A46A", "McLaren": "#FF8000", "Lexus": "#1A1A1A", "Ford": "#00274D",
    "Chevrolet": "#C5B358", "Corvette": "#C5B358", "Oreca": "#5B6670", "Ligier": "#1E2A5A",
    "Duqueine": "#6C4A9C",
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
# Points — an approximation of IMSA's per-class points curve (P1=350, sliding to
# a floor). Used only for the standings view and the standings baseline; the
# model ranks on finishing POSITIONS, which are rule-agnostic and always official.
# --------------------------------------------------------------------------- #
def _imsa_points_table(n: int = 45) -> dict[int, int]:
    table = {1: 350, 2: 320, 3: 300, 4: 280, 5: 260}
    for p in range(6, n + 1):
        table[p] = max(25, 250 - (p - 6) * 10)
    return table


FEATURE_POINTS = _imsa_points_table()

# --------------------------------------------------------------------------- #
# Model knobs (see model.py). Tuned by walk-forward validation (forward_eval /
# the never-ship-worse gate) across IMSA's modern multi-class era.
# --------------------------------------------------------------------------- #
PACE_BASE = 100.0
PACE_SPREAD = 0.55

# Endurance skill blend — an ENSEMBLE tuned by walk-forward validation (see
# forward_eval / the never-ship-worse gate). Two facts drive it:
#   * IMSA is dominated by a stable set of works/factory entries, so **recent
#     results** (the last race, this-season form) are a very strong predictor.
#   * But a single race is noisy, so a **smoothed cross-season entry rating**
#     (Elo — a car keeps its number across seasons: GTP-7 is Porsche Penske #7)
#     plus the **team's** operational quality de-noise it.
# The two naive baselines (last-race order, season-form order) are individually
# very hard to beat in endurance. A fixed-seed walk-forward sweep across 2022-2026
# showed that raising the SEASON-FORM (smoothed multi-race) weight to match the
# last-race weight makes the ensemble beat BOTH baselines on win- AND podium-Brier
# on the modern-era AND the full-history cut (margins small — the baselines are
# strong — but consistent). Elo-heavy / last-race-only blends were worse in one
# regime or the other. These weights are the validated result.
SKILL_WEIGHTS = {"last": 0.8, "elo": 0.7, "history": 0.6, "team": 0.3}

# Plackett-Luce temperature. Endurance is high-variance (mechanical attrition,
# multi-hour strategy, full-course cautions), so a slightly hotter default.
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
