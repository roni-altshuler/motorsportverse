"""
f1_prediction_utils.py  —  v2.0
================================
Shared utility module for the Formula 1 prediction project.

**v2.0 improvements over v1:**
  - StandardScaler prevents single-feature dominance
  - Team-change adjustment for drivers who switched constructors
  - Pit-strategy and tyre-degradation features
  - Circuit-specific characteristics (type, pit loss, expected stops)
  - Prediction calibration → realistic F1 gaps (≤ 3-4 s spread)
  - Current-season form tracking (earlier results feed later predictions)
  - Driver experience & qualifying-rank features
    - Complete configured-season calendar
  - HTML race-report generation

Import in any race-specific script:
    >>> from f1_prediction_utils import *
"""

# ==========================================================================
# 1. IMPORTS
# ==========================================================================
import warnings
warnings.filterwarnings("ignore")

import os
import re
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import fastf1

from leakage import assert_prior_only, LeakageError  # noqa: F401

from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

import matplotlib
matplotlib.use("Agg")          # non-interactive backend for scripts
import matplotlib.pyplot as plt
import seaborn as sns  # noqa: F401 — kept for downstream callers
from tqdm import tqdm

# Design-system rcParams (graphite + telemetry orange) — replaces the
# old sns.set_theme("whitegrid", palette="muted") vanilla look.  See
# viz_style.py for the palette + per-axis conventions.
import viz_style  # noqa: F401 — applies on import

# Ensure rcParams.dpi gets a sane default in case the viz_style module
# was imported earlier and the user overrode it.
plt.rcParams.update({"figure.figsize": (12, 6)})


# ==========================================================================
# 2. SEASON CONSTANTS (2026 BASELINE DATA)
# ==========================================================================

# ---- 2026 Official F1 Grid (11 teams, 22 drivers) -----------------------
DRIVER_TEAM_2026: dict[str, str] = {
    "VER": "Red Bull Racing",  "HAD": "Red Bull Racing",
    "NOR": "McLaren",          "PIA": "McLaren",
    "LEC": "Ferrari",          "HAM": "Ferrari",
    "ANT": "Mercedes",         "RUS": "Mercedes",
    "ALO": "Aston Martin",    "STR": "Aston Martin",
    "GAS": "Alpine",           "COL": "Alpine",
    "ALB": "Williams",         "SAI": "Williams",
    "LAW": "Racing Bulls",     "LIN": "Racing Bulls",
    "OCO": "Haas",             "BEA": "Haas",
    "BOR": "Audi",             "HUL": "Audi",
    "PER": "Cadillac",         "BOT": "Cadillac",
}

DRIVER_NUMBERS_2026: dict[str, int] = {
    "NOR": 1, "VER": 3, "BOR": 5, "HAD": 6, "GAS": 10,
    "PER": 11, "ANT": 12, "ALO": 14, "LEC": 16, "STR": 18,
    "ALB": 23, "HUL": 27, "LAW": 30, "OCO": 31, "LIN": 41,
    "COL": 43, "HAM": 44, "SAI": 55, "RUS": 63, "BOT": 77,
    "PIA": 81, "BEA": 87,
}

DRIVER_FULL_NAMES: dict[str, str] = {
    "VER": "Max Verstappen",    "HAD": "Isack Hadjar",
    "NOR": "Lando Norris",      "PIA": "Oscar Piastri",
    "LEC": "Charles Leclerc",   "HAM": "Lewis Hamilton",
    "ANT": "Kimi Antonelli",    "RUS": "George Russell",
    "ALO": "Fernando Alonso",   "STR": "Lance Stroll",
    "GAS": "Pierre Gasly",      "COL": "Franco Colapinto",
    "ALB": "Alexander Albon",   "SAI": "Carlos Sainz Jr.",
    "LAW": "Liam Lawson",       "LIN": "Arvid Lindblad",
    "OCO": "Esteban Ocon",      "BEA": "Oliver Bearman",
    "BOR": "Gabriel Bortoleto", "HUL": "Nico Hülkenberg",
    "PER": "Sergio Pérez",      "BOT": "Valtteri Bottas",
}

# ---- 2025 Final Constructor Championship Points -------------------------
CONSTRUCTOR_POINTS_2025: dict[str, int] = {
    "McLaren": 666, "Ferrari": 652, "Red Bull Racing": 589,
    "Mercedes": 468, "Aston Martin": 94, "Williams": 72,
    "Racing Bulls": 64, "Haas": 58, "Alpine": 52,
    "Audi": 12, "Cadillac": 0,
}
_max_pts = max(CONSTRUCTOR_POINTS_2025.values())
TEAM_PERFORMANCE_SCORE: dict[str, float] = {
    t: p / _max_pts for t, p in CONSTRUCTOR_POINTS_2025.items()
}

# ---- Wet-weather driver performance factor (lower = faster in wet) -------
WET_PERFORMANCE: dict[str, float] = {
    "VER": 0.975, "HAM": 0.976, "LEC": 0.976, "NOR": 0.978,
    "ALO": 0.973, "RUS": 0.969, "SAI": 0.979, "PIA": 0.978,
    "GAS": 0.979, "STR": 0.980, "ALB": 0.983, "OCO": 0.982,
    "HUL": 0.985, "LAW": 0.990, "ANT": 0.992, "HAD": 0.994,
    "BEA": 0.991, "BOR": 0.995, "COL": 0.993, "LIN": 0.994,
    "PER": 0.977, "BOT": 0.980,
}

# ---- Clean-air race pace estimates (seconds, lower = faster) -------------
CLEAN_AIR_PACE: dict[str, float] = {
    "VER": 92.8, "NOR": 93.0, "LEC": 93.1, "PIA": 93.2,
    "HAM": 93.5, "RUS": 93.4, "SAI": 93.9, "ALO": 94.5,
    "GAS": 94.3, "ALB": 94.2, "LAW": 93.8, "ANT": 94.1,
    "STR": 95.0, "HUL": 95.1, "OCO": 94.6, "HAD": 94.4,
    "BEA": 94.8, "BOR": 95.5, "COL": 94.7, "LIN": 94.9,
    "PER": 93.6, "BOT": 95.2,
}

# ---- Team colours --------------------------------------------------------
TEAM_COLOURS: dict[str, str] = {
    "Red Bull Racing": "#3671C6", "McLaren": "#FF8000",
    "Ferrari": "#E8002D",         "Mercedes": "#27F4D2",
    "Aston Martin": "#229971",    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",        "Racing Bulls": "#6692FF",
    "Haas": "#B6BABD",            "Audi": "#1E1E1E",
    "Cadillac": "#C0C0C0",
}

# ---- F1 points system (top 10) ------------------------------------------
F1_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

# ---- Official 2026 Calendar (22 rounds) ----------------------------------
CALENDAR_2026 = {
    1:  {"name": "Australian Grand Prix",     "gp_key": "Australia",      "circuit": "Albert Park",            "date": "2026-03-08", "laps": 58, "circuit_km": 5.278, "sprint": False},
    2:  {"name": "Chinese Grand Prix",        "gp_key": "China",          "circuit": "Shanghai International", "date": "2026-03-15", "laps": 56, "circuit_km": 5.451, "sprint": True,  "sprint_laps": 21},
    3:  {"name": "Japanese Grand Prix",       "gp_key": "Japan",          "circuit": "Suzuka",                 "date": "2026-03-29", "laps": 53, "circuit_km": 5.807, "sprint": False},
    4:  {"name": "Miami Grand Prix",          "gp_key": "Miami",          "circuit": "Miami International",    "date": "2026-05-03", "laps": 57, "circuit_km": 5.412, "sprint": True,  "sprint_laps": 21},
    5:  {"name": "Canadian Grand Prix",       "gp_key": "Canada",         "circuit": "Circuit Gilles Villeneuve", "date": "2026-05-24", "laps": 70, "circuit_km": 4.361, "sprint": True,  "sprint_laps": 23},
    6:  {"name": "Monaco Grand Prix",         "gp_key": "Monaco",         "circuit": "Monaco",                 "date": "2026-06-07", "laps": 78, "circuit_km": 3.337, "sprint": False},
    7:  {"name": "Barcelona-Catalunya Grand Prix", "gp_key": "Spain",     "circuit": "Barcelona-Catalunya",    "date": "2026-06-14", "laps": 66, "circuit_km": 4.657, "sprint": False},
    8:  {"name": "Austrian Grand Prix",       "gp_key": "Austria",        "circuit": "Red Bull Ring",          "date": "2026-06-28", "laps": 71, "circuit_km": 4.318, "sprint": False},
    9:  {"name": "British Grand Prix",        "gp_key": "Great Britain",  "circuit": "Silverstone",            "date": "2026-07-05", "laps": 52, "circuit_km": 5.891, "sprint": True,  "sprint_laps": 17},
    10: {"name": "Belgian Grand Prix",        "gp_key": "Belgium",        "circuit": "Spa-Francorchamps",      "date": "2026-07-19", "laps": 44, "circuit_km": 7.004, "sprint": False},
    11: {"name": "Hungarian Grand Prix",      "gp_key": "Hungary",        "circuit": "Hungaroring",            "date": "2026-07-26", "laps": 70, "circuit_km": 4.381, "sprint": False},
    12: {"name": "Dutch Grand Prix",          "gp_key": "Netherlands",    "circuit": "Zandvoort",              "date": "2026-08-23", "laps": 72, "circuit_km": 4.259, "sprint": True,  "sprint_laps": 24},
    13: {"name": "Italian Grand Prix",        "gp_key": "Italy",          "circuit": "Monza",                  "date": "2026-09-06", "laps": 53, "circuit_km": 5.793, "sprint": False},
    14: {"name": "Spanish Grand Prix",        "gp_key": "Madrid",         "circuit": "Madring",                "date": "2026-09-13", "laps": 57, "circuit_km": 5.474, "sprint": False},
    15: {"name": "Azerbaijan Grand Prix",     "gp_key": "Azerbaijan",     "circuit": "Baku City Circuit",      "date": "2026-09-27", "laps": 51, "circuit_km": 6.003, "sprint": False},
    16: {"name": "Singapore Grand Prix",      "gp_key": "Singapore",      "circuit": "Marina Bay",             "date": "2026-10-11", "laps": 62, "circuit_km": 4.940, "sprint": True,  "sprint_laps": 21},
    17: {"name": "United States Grand Prix",  "gp_key": "United States",  "circuit": "COTA",                   "date": "2026-10-25", "laps": 56, "circuit_km": 5.513, "sprint": False},
    18: {"name": "Mexico City Grand Prix",    "gp_key": "Mexico",         "circuit": "Autódromo Hermanos Rodríguez", "date": "2026-11-01", "laps": 71, "circuit_km": 4.304, "sprint": False},
    19: {"name": "São Paulo Grand Prix",      "gp_key": "Brazil",         "circuit": "Interlagos",             "date": "2026-11-08", "laps": 71, "circuit_km": 4.309, "sprint": True,  "sprint_laps": 24},
    20: {"name": "Las Vegas Grand Prix",      "gp_key": "Las Vegas",      "circuit": "Las Vegas Strip",        "date": "2026-11-21", "laps": 50, "circuit_km": 6.201, "sprint": False},
    21: {"name": "Qatar Grand Prix",          "gp_key": "Qatar",          "circuit": "Lusail",                 "date": "2026-11-29", "laps": 57, "circuit_km": 5.419, "sprint": False},
    22: {"name": "Abu Dhabi Grand Prix",      "gp_key": "Abu Dhabi",      "circuit": "Yas Marina",             "date": "2026-12-06", "laps": 58, "circuit_km": 5.281, "sprint": False},
}

# ---- Circuit characteristics (for pit / tyre / weather modelling) --------
CIRCUIT_CHARACTERISTICS: dict[str, dict] = {
    "Australia":      {"type": "street-park",  "base_quali_s": 74.8,  "expected_stops": 2, "pit_loss_s": 22.5, "tyre_deg": 0.55, "overtaking": 0.6, "drs_zones": 3, "safety_car_likelihood": 0.65, "altitude_m": 10},
    "China":          {"type": "permanent",    "base_quali_s": 93.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.60, "overtaking": 0.7, "drs_zones": 2, "safety_car_likelihood": 0.45, "altitude_m": 5},
    "Japan":          {"type": "permanent",    "base_quali_s": 88.0,  "expected_stops": 2, "pit_loss_s": 22.0, "tyre_deg": 0.65, "overtaking": 0.4, "drs_zones": 2, "safety_car_likelihood": 0.35, "altitude_m": 60},
    "Bahrain":        {"type": "permanent",    "base_quali_s": 87.0,  "expected_stops": 2, "pit_loss_s": 23.5, "tyre_deg": 0.70, "overtaking": 0.8, "drs_zones": 3, "safety_car_likelihood": 0.40, "altitude_m": 10},
    "Saudi Arabia":   {"type": "street",       "base_quali_s": 87.5,  "expected_stops": 2, "pit_loss_s": 22.0, "tyre_deg": 0.45, "overtaking": 0.5, "drs_zones": 3, "safety_car_likelihood": 0.70, "altitude_m": 15},
    "Miami":          {"type": "street-park",  "base_quali_s": 88.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.55, "overtaking": 0.6, "drs_zones": 3, "safety_car_likelihood": 0.55, "altitude_m": 2},
    "Emilia Romagna": {"type": "permanent",    "base_quali_s": 75.5,  "expected_stops": 2, "pit_loss_s": 22.0, "tyre_deg": 0.50, "overtaking": 0.4, "drs_zones": 1, "safety_car_likelihood": 0.40, "altitude_m": 47},
    "Monaco":         {"type": "street",       "base_quali_s": 70.5,  "expected_stops": 1, "pit_loss_s": 21.5, "tyre_deg": 0.30, "overtaking": 0.1, "drs_zones": 1, "safety_car_likelihood": 0.75, "altitude_m": 30},
    "Spain":          {"type": "permanent",    "base_quali_s": 76.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.70, "overtaking": 0.5, "drs_zones": 2, "safety_car_likelihood": 0.30, "altitude_m": 150},
    "Canada":         {"type": "semi-street",  "base_quali_s": 72.0,  "expected_stops": 2, "pit_loss_s": 22.5, "tyre_deg": 0.50, "overtaking": 0.7, "drs_zones": 2, "safety_car_likelihood": 0.70, "altitude_m": 13},
    "Austria":        {"type": "permanent",    "base_quali_s": 64.5,  "expected_stops": 2, "pit_loss_s": 22.0, "tyre_deg": 0.65, "overtaking": 0.7, "drs_zones": 3, "safety_car_likelihood": 0.35, "altitude_m": 700},
    "Great Britain":  {"type": "permanent",    "base_quali_s": 86.5,  "expected_stops": 2, "pit_loss_s": 22.5, "tyre_deg": 0.60, "overtaking": 0.6, "drs_zones": 2, "safety_car_likelihood": 0.30, "altitude_m": 153},
    "Belgium":        {"type": "permanent",    "base_quali_s": 105.0, "expected_stops": 2, "pit_loss_s": 23.5, "tyre_deg": 0.55, "overtaking": 0.7, "drs_zones": 2, "safety_car_likelihood": 0.40, "altitude_m": 420},
    "Hungary":        {"type": "permanent",    "base_quali_s": 76.0,  "expected_stops": 2, "pit_loss_s": 22.0, "tyre_deg": 0.60, "overtaking": 0.3, "drs_zones": 1, "safety_car_likelihood": 0.30, "altitude_m": 264},
    "Netherlands":    {"type": "permanent",    "base_quali_s": 70.0,  "expected_stops": 1, "pit_loss_s": 22.0, "tyre_deg": 0.45, "overtaking": 0.3, "drs_zones": 1, "safety_car_likelihood": 0.35, "altitude_m": 0},
    "Italy":          {"type": "permanent",    "base_quali_s": 79.5,  "expected_stops": 1, "pit_loss_s": 23.0, "tyre_deg": 0.40, "overtaking": 0.8, "drs_zones": 2, "safety_car_likelihood": 0.25, "altitude_m": 162},
    "Madrid":         {"type": "street",       "base_quali_s": 82.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.55, "overtaking": 0.5, "drs_zones": 2, "safety_car_likelihood": 0.55, "altitude_m": 650},
    "Azerbaijan":     {"type": "street",       "base_quali_s": 101.0, "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.45, "overtaking": 0.6, "drs_zones": 2, "safety_car_likelihood": 0.75, "altitude_m": -28},
    "Singapore":      {"type": "street",       "base_quali_s": 96.0,  "expected_stops": 2, "pit_loss_s": 23.5, "tyre_deg": 0.50, "overtaking": 0.4, "drs_zones": 3, "safety_car_likelihood": 0.80, "altitude_m": 15},
    "United States":  {"type": "permanent",    "base_quali_s": 94.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.60, "overtaking": 0.6, "drs_zones": 2, "safety_car_likelihood": 0.35, "altitude_m": 228},
    "Mexico":         {"type": "permanent",    "base_quali_s": 77.5,  "expected_stops": 2, "pit_loss_s": 23.5, "tyre_deg": 0.55, "overtaking": 0.5, "drs_zones": 3, "safety_car_likelihood": 0.40, "altitude_m": 2240},
    "Brazil":         {"type": "permanent",    "base_quali_s": 70.5,  "expected_stops": 2, "pit_loss_s": 22.5, "tyre_deg": 0.55, "overtaking": 0.7, "drs_zones": 2, "safety_car_likelihood": 0.55, "altitude_m": 760},
    "Las Vegas":      {"type": "street",       "base_quali_s": 93.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.40, "overtaking": 0.7, "drs_zones": 2, "safety_car_likelihood": 0.50, "altitude_m": 620},
    "Qatar":          {"type": "permanent",    "base_quali_s": 82.0,  "expected_stops": 2, "pit_loss_s": 22.5, "tyre_deg": 0.70, "overtaking": 0.5, "drs_zones": 2, "safety_car_likelihood": 0.25, "altitude_m": 12},
    "Abu Dhabi":      {"type": "semi-street",  "base_quali_s": 84.0,  "expected_stops": 2, "pit_loss_s": 23.0, "tyre_deg": 0.55, "overtaking": 0.6, "drs_zones": 2, "safety_car_likelihood": 0.35, "altitude_m": 5},
}

# ---- Team changes 2025 → 2026 (old_team, new_team) ----------------------
# Only drivers whose constructor changed.  old_team=None → rookie / out in 2025
TEAM_CHANGES_2026: dict[str, tuple] = {
    "HAM": ("Mercedes", "Ferrari"),
    "SAI": ("Ferrari",  "Williams"),
    "PER": ("Red Bull Racing", "Cadillac"),
    "OCO": ("Alpine",   "Haas"),
    "HUL": ("Haas",     "Audi"),
    "HAD": ("Racing Bulls", "Red Bull Racing"),
    "BOT": (None,       "Cadillac"),       # not on 2025 grid
    "ANT": (None,       "Mercedes"),       # rookie
    "COL": (None,       "Alpine"),         # limited 2024 experience
    "LIN": (None,       "Racing Bulls"),   # rookie
    "BEA": (None,       "Haas"),           # limited experience
    "BOR": (None,       "Audi"),           # rookie
}


# ---- Active season configuration -----------------------------------------
def _available_season_years(prefix: str) -> list[int]:
    years = []
    token = f"{prefix}_"
    for name in globals():
        if not name.startswith(token):
            continue
        suffix = name[len(token):]
        if suffix.isdigit():
            years.append(int(suffix))
    return sorted(set(years))


def _load_generated_seasons() -> None:
    """Register pre-staged future-season constants from ``generated_seasons/<year>.json``.

    ``scripts/bootstrap_next_season.py`` writes next year's calendar plus a
    carried-forward lineup there so the season rolls over with zero manual code
    edits. We inject them as module globals (``CALENDAR_<year>``,
    ``DRIVER_TEAM_<year>``, ``DRIVER_NUMBERS_<year>``) so the existing season
    scanner and rollover pick them up. ``setdefault`` means any hand-coded
    constant always wins. A pre-staged calendar does NOT become the active
    season until its first race date passes — see ``_season_started()`` /
    ``_default_season_year()``.
    """
    gen_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_seasons")
    if not os.path.isdir(gen_dir):
        return
    for fname in sorted(os.listdir(gen_dir)):
        year, ext = os.path.splitext(fname)
        if ext != ".json" or not year.isdigit():
            continue
        try:
            with open(os.path.join(gen_dir, fname), encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError):
            continue
        cal = payload.get("calendar")
        if isinstance(cal, dict) and cal:
            globals().setdefault(f"CALENDAR_{year}", {int(k): v for k, v in cal.items()})
        dt = payload.get("driver_team")
        if isinstance(dt, dict) and dt:
            globals().setdefault(f"DRIVER_TEAM_{year}", dict(dt))
        dn = payload.get("driver_numbers")
        if isinstance(dn, dict) and dn:
            globals().setdefault(f"DRIVER_NUMBERS_{year}", {k: int(v) for k, v in dn.items()})


_load_generated_seasons()


def _season_started(year: int) -> bool:
    """True once ``year``'s first race date is on/before today (UTC).

    Guards active-season selection so a pre-staged future calendar never
    hijacks the live season before it has actually begun racing.
    """
    cal = globals().get(f"CALENDAR_{year}")
    if not cal:
        return False
    dates = []
    for entry in cal.values():
        raw = entry.get("date")
        if not raw:
            continue
        try:
            dates.append(datetime.strptime(raw, "%Y-%m-%d").date())
        except (TypeError, ValueError):
            continue
    if not dates:
        return False
    return min(dates) <= datetime.utcnow().date()


def _default_season_year() -> int:
    available = _available_season_years("CALENDAR")
    if not available:
        return int(datetime.utcnow().year)
    started = [y for y in available if _season_started(y)]
    # Prefer the newest season that has actually begun; pre-staged future
    # calendars stay dormant until their opening race so the live pipeline
    # never jumps ahead of itself.
    return max(started) if started else min(available)


DEFAULT_SEASON_YEAR = _default_season_year()


def _parse_year(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


SEASON_YEAR = _parse_year(os.getenv("F1_SEASON_YEAR"), DEFAULT_SEASON_YEAR)


def _season_constant(prefix: str, year: int | None = None, *, required: bool = True, default=None):
    target_year = _parse_year(year, SEASON_YEAR)
    symbol = f"{prefix}_{target_year}"
    value = globals().get(symbol)
    if value is not None:
        return value

    if not required:
        return default

    available = _available_season_years(prefix)
    available_str = ", ".join(map(str, available)) if available else "none"
    raise ValueError(
        f"No {prefix} data found for season {target_year}. "
        f"Available seasons: {available_str}. "
        "Set F1_SEASON_YEAR or add the missing season constants."
    )


def get_season_year() -> int:
    return int(SEASON_YEAR)


def get_calendar(year: int | None = None):
    return _season_constant("CALENDAR", year)


def get_driver_team_map(year: int | None = None):
    return _season_constant("DRIVER_TEAM", year)


def get_driver_numbers_map(year: int | None = None):
    return _season_constant("DRIVER_NUMBERS", year)


def get_team_changes_map(year: int | None = None):
    return _season_constant("TEAM_CHANGES", year, required=False, default={})


# Generic active-season aliases.
CALENDAR = get_calendar()
DRIVER_TEAM = get_driver_team_map()
DRIVER_NUMBERS = get_driver_numbers_map()
TEAM_CHANGES = get_team_changes_map()

# Backward-compatible aliases for legacy call sites.
CALENDAR_2026 = CALENDAR
DRIVER_TEAM_2026 = DRIVER_TEAM
DRIVER_NUMBERS_2026 = DRIVER_NUMBERS
TEAM_CHANGES_2026 = TEAM_CHANGES

HISTORICAL_GP_ALIASES: dict[str, str] = {
    # Madrid joins the calendar before same-circuit historical telemetry exists.
    # Use Spain/Barcelona as a conservative proxy for baseline race-lap data.
    "Madrid": "Spain",
}


def resolve_historical_gp_key(grand_prix: str) -> str:
    return HISTORICAL_GP_ALIASES.get(str(grand_prix), str(grand_prix))

# ---- Driver qualifying offset from pole (fraction, smaller = faster) -----
# Used to auto-generate qualifying estimates for any circuit.
DRIVER_QUALI_OFFSET: dict[str, float] = {
    "VER": 0.000, "NOR": 0.002, "PIA": 0.001, "LEC": 0.003,
    "HAM": 0.005, "RUS": 0.004, "SAI": 0.009, "PER": 0.008,
    "ALO": 0.016, "ALB": 0.011, "LAW": 0.007, "GAS": 0.013,
    "ANT": 0.007, "STR": 0.020, "OCO": 0.017, "HUL": 0.019,
    "HAD": 0.012, "BEA": 0.016, "COL": 0.021, "LIN": 0.023,
    "BOR": 0.024, "BOT": 0.021,
}

# ---- Driver experience (career F1 race starts as of end-2025) -----------
DRIVER_EXPERIENCE: dict[str, int] = {
    "HAM": 353, "ALO": 400, "VER": 210, "BOT": 240, "PER": 280,
    "RUS": 110, "NOR": 130, "LEC": 145, "STR": 170, "GAS": 150,
    "OCO": 140, "ALB": 80,  "HUL": 225, "SAI": 200, "PIA": 50,
    "LAW": 25,  "HAD": 0,   "ANT": 0,   "COL": 10,  "LIN": 0,
    "BEA": 15,  "BOR": 0,
}

# ---- Team pit-stop speed ranking (seconds, lower = faster crew) ---------
TEAM_PIT_SPEED: dict[str, float] = {
    "Red Bull Racing": 2.1, "McLaren": 2.3, "Ferrari": 2.4,
    "Mercedes": 2.3, "Aston Martin": 2.6, "Alpine": 2.7,
    "Williams": 2.5, "Racing Bulls": 2.5, "Haas": 2.8,
    "Audi": 2.9, "Cadillac": 3.0,
}

# ---- Default feature columns (v3 — race-to-race scalable) ----------------
DEFAULT_FEATURE_COLS: list[str] = [
    "TeamAdjustedPace",
    "TeamPerformanceScore",
    "TeamFormDelta",
    "CleanAirPace",
    "BestLapTime",
    "LapTimeStd",
    "ConsistencyScore",
    "SectorBalance",
    "PitTimeLoss",
    "TyreDegFactor",
    "ExperienceFactor",
    "RainProbability",
    "Temperature",
    "WeatherRiskScore",
    "CircuitOvertaking",
    "CircuitSafetyCar",
    "CircuitGripPenalty",
    "ExpectedStopsFeature",
    "SprintWeekend",
    "QualifyingRank",
    "GridAdvantage",
    "CurrentForm",
    "PreviousPosition",
    "SeasonMomentum",
    "PositionTrend",
    "DriverPredictionBias",
    "TeamPredictionBias",
    "DriverDegComposite",
    "DriverDegDeltaField",
    "UndercutEdgeAhead",
    "OvercutEdgeBehind",
    "TeamOrderPressure",
    "TeammateConflictRisk",
    "FieldPositionVolatility",
    "LocalBattleIntensity",
    "DRSOvertakeProbAhead",
    # ---- Elo features (added 2026-05-25) ------------------------------
    # Populated by _add_elo_features() from prior-round actual + predicted
    # results; default to neutral values for rookies / missing history.
    "driver_elo",
    "team_elo",
    "driver_form_elo",
    "wet_weather_elo",
    "qualifying_elo",
    "racecraft_elo",
    "teammate_delta_elo",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DATA_DIR = os.path.join(PROJECT_ROOT, "website", "public", "data")

# Canonical state files (absolute paths so CWD does not matter)
SEASON_RESULTS_FILE = os.path.join(PROJECT_ROOT, f"season_results_{SEASON_YEAR}.json")
PREDICTED_RESULTS_FILE = os.path.join(PROJECT_ROOT, f"predicted_results_{SEASON_YEAR}.json")

# Mirrored state files under website/public/data for transparency/debugging
SEASON_RESULTS_WEBSITE_FILE = os.path.join(WEBSITE_DATA_DIR, f"season_results_{SEASON_YEAR}.json")
PREDICTED_RESULTS_WEBSITE_FILE = os.path.join(WEBSITE_DATA_DIR, f"predicted_results_{SEASON_YEAR}.json")


def _read_json_file(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_file(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _normalize_round_results(raw):
    """Normalize round-position maps into {"<round>": {"DRV": int_pos}}."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for rnd_key, rnd_data in raw.items():
        try:
            rnd = int(rnd_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(rnd_data, dict):
            continue
        parsed = {}
        for drv, pos in rnd_data.items():
            value = pos.get("position") if isinstance(pos, dict) else pos
            try:
                parsed[str(drv)] = int(value)
            except (TypeError, ValueError):
                continue
        if parsed:
            out[str(rnd)] = parsed
    return out


def _load_season_position_maps(current_round=None):
    """Load predicted, actual, and merged position maps with graceful fallback."""
    pred_candidates = [
        PREDICTED_RESULTS_FILE,
        PREDICTED_RESULTS_WEBSITE_FILE,
        f"predicted_results_{SEASON_YEAR}.json",
    ]
    actual_candidates = [
        SEASON_RESULTS_FILE,
        SEASON_RESULTS_WEBSITE_FILE,
        f"season_results_{SEASON_YEAR}.json",
    ]

    predicted = {}
    for path in pred_candidates:
        predicted = _normalize_round_results(_read_json_file(path))
        if predicted:
            break

    actual = {}
    for path in actual_candidates:
        actual = _normalize_round_results(_read_json_file(path))
        if actual:
            break

    combined = dict(predicted)
    for rnd_str, rnd_data in actual.items():
        combined[rnd_str] = rnd_data

    if current_round is not None:
        predicted = {
            rnd: data
            for rnd, data in predicted.items()
            if int(rnd) < current_round
        }
        actual = {
            rnd: data
            for rnd, data in actual.items()
            if int(rnd) < current_round
        }
        combined = {
            rnd: data
            for rnd, data in combined.items()
            if int(rnd) < current_round
        }
        # Defence in depth: ensure the filter actually held.  If a future
        # refactor breaks the filter above this assertion catches it.
        assert_prior_only(predicted, current_round, "predicted_results")
        assert_prior_only(actual, current_round, "actual_results")
        assert_prior_only(combined, current_round, "combined_results")

    return predicted, actual, combined


def _add_dynamic_team_form(merged, combined_results=None, current_round=1):
    """Blend static constructor strength with recency-weighted season form."""
    merged = merged.copy()
    merged["TeamFormDelta"] = 0.0

    if current_round <= 1:
        return merged

    if combined_results is None:
        _, _, combined_results = _load_season_position_maps(current_round=current_round)

    if not combined_results:
        return merged

    weighted_points = {team: 0.0 for team in TEAM_PERFORMANCE_SCORE}
    weighted_counts = {team: 0.0 for team in TEAM_PERFORMANCE_SCORE}

    for rnd_str, rnd_data in combined_results.items():
        rnd = int(rnd_str)
        if rnd >= current_round:
            continue
        weight = float(np.exp(0.25 * rnd))
        for drv, pos in rnd_data.items():
            team = DRIVER_TEAM.get(drv)
            if team is None:
                continue
            weighted_points[team] += F1_POINTS.get(int(pos), 0) * weight
            weighted_counts[team] += weight

    avg_points = {
        team: (weighted_points[team] / weighted_counts[team])
        for team in TEAM_PERFORMANCE_SCORE
        if weighted_counts[team] > 0
    }
    if not avg_points:
        return merged

    max_avg = max(avg_points.values())
    if max_avg <= 0:
        return merged

    dynamic_scores = {}
    for team, base in TEAM_PERFORMANCE_SCORE.items():
        recent_norm = avg_points.get(team, 0.0) / max_avg
        dynamic_scores[team] = 0.65 * base + 0.35 * recent_norm

    merged["TeamFormDelta"] = merged["Team"].map(
        lambda t: dynamic_scores.get(t, TEAM_PERFORMANCE_SCORE.get(t, 0.0))
        - TEAM_PERFORMANCE_SCORE.get(t, 0.0)
    )
    merged["TeamPerformanceScore"] = merged["Team"].map(
        lambda t: dynamic_scores.get(t, TEAM_PERFORMANCE_SCORE.get(t, 0.0))
    )
    print("✅ Dynamic team-form blend applied from prior rounds.")
    return merged


def _add_elo_features(merged, combined_results, current_round, current_season):
    """Compute the seven Elo features from prior-round results.

    Populates ``driver_elo``, ``team_elo``, ``driver_form_elo``,
    ``wet_weather_elo``, ``qualifying_elo``, ``racecraft_elo``,
    ``teammate_delta_elo`` on ``merged``. Drivers with no prior-round
    record (rookies, mid-season swaps) inherit the team-mean rating
    via :meth:`models.elo.DriverElo.initialise_rookie` minus a small
    discount. The feature is leakage-safe: ``combined_results`` is
    already filtered to ``round < current_round`` by the caller.

    The Elo system in this iteration uses **current-season results
    only** — multi-season bootstrap would need per-season team
    mappings which we do not currently store. Adding that is a
    natural follow-up.
    """
    from models.elo import EloFeatureBuilder, RaceEvent, ELO_FEATURE_COLUMNS

    builder = EloFeatureBuilder()

    # Replay prior rounds. The race "wet" flag isn't currently stored
    # in combined_results — leave it False until a wet-race indicator
    # is plumbed through. wet_weather_elo will reflect 1500 for now
    # but still be a usable z-score after the postprocessor scales it.
    sorted_rounds = sorted(combined_results.keys(), key=lambda r: int(r))
    events: list[RaceEvent] = []
    for rnd_str in sorted_rounds:
        rnd = int(rnd_str)
        race_data = combined_results.get(rnd_str, {})
        if not isinstance(race_data, dict) or not race_data:
            continue
        finish_order = {
            drv: int(pos)
            for drv, pos in race_data.items()
            if drv in DRIVER_TEAM and isinstance(pos, (int, float))
        }
        if len(finish_order) < 2:
            continue
        # Grid order is not stored in combined_results. We deliberately pass
        # None here rather than finish_order — feeding the finish positions in
        # as a grid proxy collapsed qualifying_elo and racecraft_elo into
        # noisy duplicates of driver_elo (audit 2026-05-25). The Elo builder
        # now skips those two updates when grid_order is None; they will
        # resume updating once a real grid source is plumbed through
        # combine_results_data.
        grid_order = None
        team_of = {drv: DRIVER_TEAM[drv] for drv in finish_order}
        events.append(
            RaceEvent(
                season=current_season,
                round=rnd,
                finish_order=finish_order,
                grid_order=grid_order,
                team_of=team_of,
                wet=False,
            )
        )

    if events:
        builder.replay_history(
            events,
            current_season=current_season,
            current_round=current_round,
        )

    # Seed any drivers that haven't competed yet (rookies, new entries).
    roster = {drv: team for drv, team in DRIVER_TEAM.items() if drv in set(merged["Driver"])}
    builder.ensure_rookies(roster)

    # Each row in merged describes one driver; pull teammate from
    # DRIVER_TEAM (same-team driver other than self).
    def _teammate_of(driver: str) -> str | None:
        team = DRIVER_TEAM.get(driver)
        if team is None:
            return None
        for drv, t in DRIVER_TEAM.items():
            if t == team and drv != driver:
                return drv
        return None

    feature_arrays: dict[str, list[float]] = {col: [] for col in ELO_FEATURE_COLUMNS}
    for _, row in merged.iterrows():
        drv = row["Driver"]
        team = DRIVER_TEAM.get(drv, row.get("Team", ""))
        teammate = _teammate_of(drv)
        feats = builder.features_for(drv, team, teammate)
        for col in ELO_FEATURE_COLUMNS:
            feature_arrays[col].append(feats[col])

    for col, values in feature_arrays.items():
        merged[col] = values

    print(
        f"✅ Elo features added — replayed {len(events)} prior round(s) "
        f"for season {current_season}."
    )
    return merged


def _add_prediction_bias_features(
    merged, predicted_results, actual_results, *, current_round=None
):
    """Add driver/team bias features from historical prediction residuals.

    The ``current_round`` argument is required to enforce leakage
    discipline at the boundary: if either ``predicted_results`` or
    ``actual_results`` contains a key at or beyond ``current_round``,
    a :class:`LeakageError` fires. When ``current_round=None`` the
    assertion is skipped to preserve backward compatibility with the
    handful of unit tests that build the bias features directly.
    """
    merged = merged.copy()

    if current_round is not None:
        assert_prior_only(predicted_results, current_round, "bias_predicted_results")
        assert_prior_only(actual_results, current_round, "bias_actual_results")

    driver_sum = {drv: 0.0 for drv in DRIVER_TEAM}
    driver_weight = {drv: 0.0 for drv in DRIVER_TEAM}

    for rnd_str, pred_round in predicted_results.items():
        actual_round = actual_results.get(rnd_str, {})
        if not pred_round or not actual_round:
            continue
        rnd = int(rnd_str)
        weight = float(np.exp(0.35 * rnd))
        for drv, pred_pos in pred_round.items():
            if drv not in actual_round:
                continue
            # Positive value means driver usually finishes better than predicted.
            residual = float(pred_pos) - float(actual_round[drv])
            if drv not in driver_sum:
                continue
            driver_sum[drv] += residual * weight
            driver_weight[drv] += weight

    driver_bias = {
        drv: (driver_sum[drv] / driver_weight[drv]) if driver_weight[drv] > 0 else 0.0
        for drv in DRIVER_TEAM
    }

    team_sum = {team: 0.0 for team in TEAM_PERFORMANCE_SCORE}
    team_count = {team: 0 for team in TEAM_PERFORMANCE_SCORE}
    for drv, bias in driver_bias.items():
        team = DRIVER_TEAM.get(drv)
        if team is None:
            continue
        team_sum[team] += bias
        team_count[team] += 1
    team_bias = {
        team: (team_sum[team] / team_count[team]) if team_count[team] > 0 else 0.0
        for team in TEAM_PERFORMANCE_SCORE
    }

    merged["DriverPredictionBias"] = merged["Driver"].map(driver_bias).fillna(0.0)
    merged["TeamPredictionBias"] = merged["Team"].map(team_bias).fillna(0.0)
    print("✅ Historical prediction-bias features added.")
    return merged


# ==========================================================================
# 3. DATA LOADING
# ==========================================================================

def enable_cache(cache_dir: str = "f1_cache") -> None:
    """Enable the FastF1 local cache directory."""
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    print(f"✅ FastF1 cache enabled at ./{cache_dir}")


# Committed offline lap store.  The historical race laps that feed the
# per-circuit driver-pace features are IMMUTABLE, but the FastF1 live-timing
# API is frequently unreachable from CI runners (GitHub Actions egress IPs get
# empty responses and get rate-limited), which used to crash the whole
# race-weekend cron in load_multi_year_data with "No data for <GP>".  We
# therefore materialise each past session's laps to a committed parquet under
# features/data/lap_cache/ and read from it first, so downstream builds never
# depend on the network for closed seasons — the monorepo rule: "committed
# snapshot is the offline source of truth".  A live fetch (when run somewhere
# with network access) writes the snapshot so it can be committed for CI.
LAP_CACHE_DIR = Path(__file__).resolve().parent.parent / "features" / "data" / "lap_cache"


def _lap_cache_path(year, grand_prix, session_type: str = "R") -> Path:
    """Committed-snapshot path for one (year, circuit, session).

    Keyed on the *resolved* historical GP so aliased circuits (e.g. Madrid →
    Spain) share a single snapshot.
    """
    historical_gp = resolve_historical_gp_key(grand_prix)
    safe_gp = re.sub(r"[^0-9A-Za-z]+", "_", str(historical_gp)).strip("_")
    return LAP_CACHE_DIR / f"{year}_{safe_gp}_{session_type}.parquet"


def _write_lap_cache(cache_path: Path, laps) -> None:
    """Best-effort persist of a freshly-fetched session to the offline store."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        laps.to_parquet(cache_path, index=False)
    except Exception as exc:  # pragma: no cover - persistence is best-effort
        print(f"  ⚠️  Could not write lap cache {cache_path.name}: {exc}")


def load_race_session(year, grand_prix, session_type="R"):
    """Load a single FastF1 session → DataFrame of lap/sector times.

    Prefers the committed offline snapshot (features/data/lap_cache/) so CI
    never touches the FastF1 network for immutable past seasons; falls back to
    a live FastF1 fetch (and writes the snapshot) when no snapshot exists.
    """
    cache_path = _lap_cache_path(year, grand_prix, session_type)
    if cache_path.exists():
        laps = pd.read_parquet(cache_path)
        print(f"  ✅ {year} {grand_prix} — {len(laps)} laps (offline snapshot).")
        return laps

    historical_gp = resolve_historical_gp_key(grand_prix)
    alias_note = f" via {historical_gp}" if historical_gp != grand_prix else ""
    print(f"  ⏳ Loading {year} {grand_prix} GP ({session_type}){alias_note} …")
    session = fastf1.get_session(year, historical_gp, session_type)
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    cols = ["Driver", "LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]
    laps = session.laps[cols].copy()
    laps.dropna(inplace=True)
    for c in ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time"]:
        laps[f"{c} (s)"] = laps[c].dt.total_seconds()
    laps["Year"] = year
    print(f"  ✅ {year} {grand_prix} — {len(laps)} laps loaded.")
    _write_lap_cache(cache_path, laps)
    return laps


def load_multi_year_data(grand_prix, years=None, session_type="R"):
    """Load and concatenate race data across multiple seasons."""
    if years is None:
        years = [2023, 2024, 2025]
    frames = []
    for yr in tqdm(years, desc="Loading seasons", unit="season"):
        try:
            frames.append(load_race_session(yr, grand_prix, session_type))
        except Exception as exc:
            print(f"  ⚠️  Could not load {yr} {grand_prix}: {exc}")
    if not frames:
        raise RuntimeError(f"No data for {grand_prix} ({years}).")
    combined = pd.concat(frames, ignore_index=True)
    print(f"\n📊 Combined dataset: {len(combined)} laps across "
          f"{combined['Year'].nunique()} season(s).")
    return combined


# ==========================================================================
# 4. FEATURE ENGINEERING  (v2 — team-adjusted, pit/tyre, experience)
# ==========================================================================

def aggregate_driver_stats(laps):
    """Aggregate raw lap data → per-driver mean stats."""
    drivers = laps["Driver"].unique()
    rows = []
    for drv in tqdm(drivers, desc="Aggregating driver stats", unit="driver"):
        d = laps[laps["Driver"] == drv]
        rows.append({
            "Driver": drv,
            "AvgLapTime": d["LapTime (s)"].mean(),
            "BestLapTime": d["LapTime (s)"].min(),
            "LapTimeStd": d["LapTime (s)"].std(),
            "Sector1": d["Sector1Time (s)"].mean(),
            "Sector2": d["Sector2Time (s)"].mean(),
            "Sector3": d["Sector3Time (s)"].mean(),
            "LapCount": len(d),
        })
    stats = pd.DataFrame(rows)
    stats["TotalSectorTime"] = stats["Sector1"] + stats["Sector2"] + stats["Sector3"]
    stats["ConsistencyScore"] = stats["LapTimeStd"] / stats["AvgLapTime"]
    stats["SectorBalance"] = (
        stats[["Sector1", "Sector2", "Sector3"]].std(axis=1) /
        stats[["Sector1", "Sector2", "Sector3"]].mean(axis=1)
    )
    print(f"✅ Aggregated stats for {len(stats)} unique drivers.")
    return stats


def build_grid_dataframe():
    """Create a season-grid DataFrame with enriched features."""
    grid = pd.DataFrame(
        [{"Driver": c, "Team": t} for c, t in DRIVER_TEAM.items()]
    )
    grid["DriverName"]           = grid["Driver"].map(DRIVER_FULL_NAMES)
    grid["DriverNumber"]         = grid["Driver"].map(DRIVER_NUMBERS)
    grid["TeamPerformanceScore"] = grid["Team"].map(TEAM_PERFORMANCE_SCORE)
    grid["CleanAirPace"]         = grid["Driver"].map(CLEAN_AIR_PACE)
    grid["WetPerformance"]       = grid["Driver"].map(WET_PERFORMANCE)
    return grid


def _apply_team_change_adjustment(merged):
    """Adjust historical lap / sector times for drivers who changed teams.

    If a driver moved from a stronger team to a weaker one, their raw
    historical times need to be *increased* (they'll be slower in a worse
    car).  Conversely, a move to a better team → slightly faster.

    Factor: 1 + alpha * (old_score - new_score),  alpha = 0.08
    Rookies (old_team=None) get a +2 % rookie penalty on imputed times.
    """
    ALPHA  = 0.08   # sensitivity to team-strength delta
    ROOKIE = 1.02   # +2 % penalty for no historical data

    factors = {}
    for drv, _team in DRIVER_TEAM.items():
        if drv in TEAM_CHANGES:
            old_team, new_team = TEAM_CHANGES[drv]
            if old_team is None:
                factors[drv] = ROOKIE            # rookie
            else:
                old_s = TEAM_PERFORMANCE_SCORE.get(old_team, 0.0)
                new_s = TEAM_PERFORMANCE_SCORE.get(new_team, 0.0)
                factors[drv] = 1.0 + ALPHA * (old_s - new_s)
        else:
            factors[drv] = 1.0                   # stayed at same team

    merged = merged.copy()
    merged["TeamChangeFactor"] = merged["Driver"].map(factors)

    time_cols = ["AvgLapTime", "Sector1", "Sector2", "Sector3", "TotalSectorTime"]
    for col in time_cols:
        merged[col] = merged[col] * merged["TeamChangeFactor"]

    # Build team-adjusted pace column (key model feature)
    merged["TeamAdjustedPace"] = merged["TotalSectorTime"]

    print("✅ Team-change adjustments applied.")
    return merged


def _add_pit_and_tyre_features(merged, circuit_key="Australia"):
    """Add pit-strategy and tyre-degradation features."""
    char = CIRCUIT_CHARACTERISTICS.get(circuit_key, {})
    expected_stops = char.get("expected_stops", 2)
    pit_loss       = char.get("pit_loss_s", 23.0)
    tyre_deg       = char.get("tyre_deg", 0.55)

    merged = merged.copy()
    # Total time lost to pit stops (pit entry/exit + stationary)
    merged["PitTimeLoss"] = merged["Team"].map(TEAM_PIT_SPEED).fillna(2.8)
    merged["PitTimeLoss"] = (merged["PitTimeLoss"] + pit_loss) * expected_stops

    # Tyre degradation factor — how much the circuit punishes tyre wear
    # Teams with better constructors tend to manage tyres better
    merged["TyreDegFactor"] = tyre_deg * (2.0 - merged["TeamPerformanceScore"])

    # Experience factor (log-scaled)
    merged["ExperienceFactor"] = merged["Driver"].map(DRIVER_EXPERIENCE)
    merged["ExperienceFactor"] = np.log1p(merged["ExperienceFactor"].fillna(0))

    print(f"✅ Pit/tyre/experience features added (circuit: {circuit_key}, "
          f"{expected_stops} stops, tyre deg={tyre_deg:.2f}).")
    return merged


def _add_circuit_context_features(merged, circuit_key="Australia", sprint=False):
    """Add track-specific context so the model can behave differently by venue."""
    char = CIRCUIT_CHARACTERISTICS.get(circuit_key, {})
    merged = merged.copy()
    merged["CircuitOvertaking"] = char.get("overtaking", 0.5)
    merged["CircuitSafetyCar"] = char.get("safety_car_likelihood", 0.4)
    merged["CircuitGripPenalty"] = 1.0 - char.get("overtaking", 0.5) + char.get("tyre_deg", 0.5) * 0.5
    merged["ExpectedStopsFeature"] = char.get("expected_stops", 2)
    merged["SprintWeekend"] = 1.0 if sprint else 0.0
    return merged


def _add_current_season_form(merged, current_round=1, combined_results=None):
    """Incorporate results from earlier races in the active season (predicted or actual).

    v3: Reads from both actual and predicted season result files. Actual
    results take
    priority when available.  This makes the model truly scalable
    race-to-race — each round's predictions auto-feed the next.

    At round 1 this feature is neutral for everyone (no data yet).
    """
    merged = merged.copy()
    form = {}

    if combined_results is None:
        _, _, combined_results = _load_season_position_maps(current_round=current_round)

    if combined_results and current_round > 1:
        for drv in DRIVER_TEAM:
            positions = []
            weights   = []
            for rnd_str, rnd_data in combined_results.items():
                rnd = int(rnd_str)
                if rnd < current_round and drv in rnd_data:
                    positions.append(rnd_data[drv])
                    # Exponential recency: more recent rounds much heavier
                    weights.append(np.exp(0.3 * rnd))
            if positions:
                form[drv] = np.average(positions, weights=weights)
            else:
                form[drv] = 11.0   # neutral default (mid-grid)
    else:
        for drv in DRIVER_TEAM:
            form[drv] = 11.0       # no data for round 1

    merged["CurrentForm"] = merged["Driver"].map(form)
    completed = current_round - 1
    source = "predicted+actual" if combined_results else "none"
    print(f"✅ Current season form added ({completed} race(s), source={source}).")
    return merged


def _add_race_to_race_features(merged, current_round=1, combined_results=None):
    """Add features that capture driver trajectory across the season.

    v3 NEW — These features make the model truly scalable race-to-race:
      - PreviousPosition: finishing position in the immediately prior round
      - SeasonMomentum:   weighted trend (improving vs declining)
      - PositionTrend:    slope of position over recent rounds (negative=improving)
    """
    merged = merged.copy()

    if combined_results is None:
        _, _, combined_results = _load_season_position_maps(current_round=current_round)

    prev_pos = {}
    momentum = {}
    trend = {}

    for drv in DRIVER_TEAM:
        # Gather all positions for this driver before current_round
        positions_by_round = []
        for rnd in range(1, current_round):
            rnd_str = str(rnd)
            if rnd_str in combined_results and drv in combined_results[rnd_str]:
                positions_by_round.append((rnd, combined_results[rnd_str][drv]))

        if not positions_by_round:
            prev_pos[drv] = 11.0    # neutral
            momentum[drv] = 0.0     # no momentum data
            trend[drv] = 0.0        # no trend
        else:
            # Previous position (last completed round)
            prev_pos[drv] = float(positions_by_round[-1][1])

            # Momentum: compare recent avg to early avg
            if len(positions_by_round) >= 2:
                recent = [p for _, p in positions_by_round[-3:]]  # last 3
                early  = [p for _, p in positions_by_round[:3]]   # first 3
                # Negative = improving (lower position number = better)
                momentum[drv] = np.mean(early) - np.mean(recent)
            else:
                momentum[drv] = 0.0

            # Position trend: linear regression slope over all rounds
            if len(positions_by_round) >= 2:
                rounds = np.array([r for r, _ in positions_by_round])
                pos_arr = np.array([p for _, p in positions_by_round])
                # Slope: negative = improving over time
                slope = np.polyfit(rounds, pos_arr, 1)[0]
                trend[drv] = float(slope)
            else:
                trend[drv] = 0.0

    merged["PreviousPosition"] = merged["Driver"].map(prev_pos)
    merged["SeasonMomentum"]   = merged["Driver"].map(momentum)
    merged["PositionTrend"]    = merged["Driver"].map(trend)

    n_prior = max(0, current_round - 1)
    print(f"✅ Race-to-race features added (PreviousPosition, SeasonMomentum, "
          f"PositionTrend from {n_prior} prior round(s)).")
    return merged


def build_training_dataset(grid, driver_stats, circuit_key="Australia",
                           current_round=1, sprint=False):
    """Merge grid + historical stats + all engineered features.

    v3 improvements:
      - team-change adjustment
      - pit / tyre / experience features
      - current-season form (from predicted + actual results)
      - race-to-race features: PreviousPosition, SeasonMomentum, PositionTrend
    """
    if not isinstance(current_round, int) or current_round < 1:
        raise LeakageError(
            f"build_training_dataset requires a positive integer current_round; "
            f"got {current_round!r}. Without it, history filtering is bypassed "
            f"and the model can train on its own future."
        )
    merged = grid.merge(driver_stats, on="Driver", how="left")

    # Impute missing historical data (rookies / new drivers)
    hist_cols = ["AvgLapTime", "BestLapTime", "LapTimeStd", "ConsistencyScore",
                 "Sector1", "Sector2", "Sector3", "SectorBalance",
                 "TotalSectorTime", "LapCount"]
    imputer = SimpleImputer(strategy="median")
    merged[hist_cols] = imputer.fit_transform(merged[hist_cols])

    # Team-change adjustment (modifies time columns)
    merged = _apply_team_change_adjustment(merged)

    predicted_results, actual_results, combined_results = _load_season_position_maps(
        current_round=current_round
    )

    # Dynamic constructor form from ongoing season results.
    merged = _add_dynamic_team_form(
        merged, combined_results=combined_results, current_round=current_round
    )

    # Pit / tyre / experience
    merged = _add_pit_and_tyre_features(merged, circuit_key=circuit_key)

    # Circuit context
    merged = _add_circuit_context_features(
        merged, circuit_key=circuit_key, sprint=sprint
    )

    # Current season form
    merged = _add_current_season_form(
        merged, current_round=current_round, combined_results=combined_results
    )

    # Race-to-race features
    merged = _add_race_to_race_features(
        merged, current_round=current_round, combined_results=combined_results
    )

    # Historical prediction residuals help correct recurring over/under-rating.
    merged = _add_prediction_bias_features(
        merged, predicted_results, actual_results, current_round=current_round
    )

    # Elo ratings derived from prior-round finish orders. Adds the seven
    # ELO_FEATURE_COLUMNS to merged; rookies are seeded from team mean.
    merged = _add_elo_features(
        merged,
        combined_results=combined_results,
        current_round=current_round,
        current_season=SEASON_YEAR,
    )

    print(f"✅ Training dataset built — {len(merged)} drivers, "
          f"{len(DEFAULT_FEATURE_COLS)} features.")
    return merged


# ==========================================================================
# 5. QUALIFYING DATA — AUTOMATIC INGESTION (with date guard + timeout)
# ==========================================================================

# Cache of the most recently-fetched official grid order, keyed by
# "<year>:<grand_prix>".  Populated by ``fetch_qualifying_data`` (no extra
# FastF1 load) and read by ``get_last_qualifying_grid`` so the export pipeline
# can seat no-time drivers from the real grid without re-loading the session.
_QUALI_GRID_CACHE: dict = {}


def _extract_qualifying_grid(session):
    """Best-effort {driver: official grid/quali position} from a Q session.

    Reads ``session.results`` (FastF1) which carries the classified
    qualifying order *including* drivers who set no lap (they appear at the
    back, e.g. P21/P22).  Returns ``{}`` when results are unavailable.
    """
    try:
        res = getattr(session, "results", None)
        if res is None or len(res) == 0:
            return {}
        grid = {}
        for _, row in res.iterrows():
            drv = row.get("Abbreviation")
            if not drv:
                continue
            pos = row.get("Position")
            if pos is None or (isinstance(pos, float) and np.isnan(pos)):
                pos = row.get("GridPosition")
            if pos is None or (isinstance(pos, float) and np.isnan(pos)):
                continue
            grid[str(drv)] = int(pos)
        return grid
    except Exception:
        return {}


def get_last_qualifying_grid(year, grand_prix):
    """Return the official grid order captured by the last fetch, or ``{}``."""
    return dict(_QUALI_GRID_CACHE.get(f"{year}:{grand_prix}", {}))


# Jolpica/Ergast is the same timely source the website's qualifying *table*
# already trusts. FastF1 telemetry for the current weekend lags hours behind
# Jolpica's classified results, so we fall back to Jolpica for the model's
# qualifying input — otherwise the published forecast silently runs on
# estimates while the official quali order is already on the page.
_JOLPICA_BASE_URL = "https://api.jolpi.ca/ergast/f1"


def _resolve_round_number(grand_prix):
    """Map a grand-prix name / gp_key to its calendar round number, or None."""
    needle = (grand_prix or "").lower()
    for rnd, info in CALENDAR.items():
        if needle == info.get("gp_key", "").lower() or needle in info["name"].lower():
            return rnd
    return None


def _parse_laptime_to_seconds(value):
    """Parse a ``"M:SS.mmm"`` (or ``"SS.mmm"``) lap string to float seconds.

    Returns ``None`` for blanks / unparseable values so callers can skip
    no-time entries (Jolpica emits ``null`` or ``""`` for sessions a driver
    did not set a lap in).
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if ":" in text:
            minutes, seconds = text.split(":", 1)
            return int(minutes) * 60 + float(seconds)
        return float(text)
    except (ValueError, TypeError):
        return None


def _fastf1_session_matches_round(session, expected_round):
    """True when a FastF1 session's resolved event round matches ``expected_round``.

    Mirrors ``gp_weekend._event_matches_round`` so the low-level qualifying fetch
    enforces the same wrong-event guard the phase detector already applies.
    """
    try:
        return int(session.event["RoundNumber"]) == int(expected_round)
    except (KeyError, TypeError, ValueError):
        return False


def _fetch_qualifying_from_jolpica(year, grand_prix, expected_round=None):
    """Fetch official qualifying times from Jolpica/Ergast as a FastF1 fallback.

    Returns ``{driver_code: best_lap_seconds}`` for drivers who set a valid lap
    (best of Q3 → Q2 → Q1), and — as a side-effect — caches the full classified
    grid order (incl. no-time drivers at the back) for ``get_last_qualifying_grid``.
    Returns ``None`` when Jolpica has no qualifying data for the round yet.

    The Jolpica endpoint is round-scoped by URL, so it cannot fuzzy-match a
    wrong event the way FastF1 can. As defence-in-depth we still verify the
    round the payload echoes back matches ``expected_round`` when supplied.
    """
    from urllib.request import urlopen

    rnd = _resolve_round_number(grand_prix)
    if rnd is None:
        return None
    if expected_round is not None and int(rnd) != int(expected_round):
        # The name→round resolution itself disagrees with the caller — refuse.
        return None
    try:
        url = f"{_JOLPICA_BASE_URL}/{year}/{int(rnd)}/qualifying.json"
        with urlopen(url, timeout=20) as response:
            payload = json.load(response)
        races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            return None
        if expected_round is not None:
            try:
                echoed = int(races[0].get("round"))
            except (TypeError, ValueError):
                echoed = None
            if echoed != int(expected_round):
                print(f"🛑 Jolpica qualifying echoed round {echoed}, expected "
                      f"{expected_round} — rejecting.")
                return None
        results = races[0].get("QualifyingResults", [])
        if not results:
            return None
    except Exception as exc:
        print(f"⚠️  Jolpica qualifying unavailable: {type(exc).__name__}")
        return None

    best = {}
    grid = {}
    for entry in results:
        code = (entry.get("Driver") or {}).get("code")
        if not code:
            continue
        times = [
            _parse_laptime_to_seconds(entry.get(key))
            for key in ("Q3", "Q2", "Q1")
        ]
        times = [t for t in times if t is not None]
        if times:
            best[code] = min(times)
        try:
            grid[code] = int(entry.get("position"))
        except (TypeError, ValueError):
            pass

    if grid:
        _QUALI_GRID_CACHE[f"{year}:{grand_prix}"] = grid
    if best:
        print(f"🏁 Qualifying data fetched from Jolpica — {len(best)} drivers "
              "with valid laps (FastF1 fallback).")
        return best
    return None


# ── Verified-qualifying override (walk-forward regeneration seam) ──────────
# regenerate_post_quali.py injects each round's OFFICIAL qualifying data here,
# sourced from the committed round JSON's weekendResults (round-scoped by
# construction, originally ingested from Jolpica/FastF1 with round guards).
# This keeps the leakage-safe replay deterministic and offline-safe without
# hammering FastF1's rate limit. Keyed "<year>:<gp_key>".
_QUALI_TIMES_OVERRIDE: dict = {}


def set_qualifying_override(year, grand_prix, times, grid=None):
    """Inject verified official qualifying data for ``(year, grand_prix)``.

    ``times``: {driver_code: best_lap_seconds}; ``grid``: {driver_code: position}.
    Only call this with round-verified official data — the override is treated
    as real qualifying (``real-quali-verified`` provenance) downstream.
    """
    key = f"{int(year)}:{grand_prix}"
    _QUALI_TIMES_OVERRIDE[key] = dict(times)
    if grid:
        _QUALI_GRID_CACHE[key] = dict(grid)


def clear_qualifying_overrides():
    """Remove all injected qualifying overrides (test/regeneration hygiene)."""
    _QUALI_TIMES_OVERRIDE.clear()


def fetch_qualifying_data(year, grand_prix, expected_round=None):
    """Try to fetch qualifying data from FastF1 (with date guard + timeout).

    Returns a ``{driver: best_lap_seconds}`` dict for drivers who set a valid
    lap.  Drivers with NO valid lap (DNS, all laps deleted, missing telemetry)
    are deliberately **excluded** so downstream logic can treat them as
    no-time runners rather than silently optimistic estimates.  As a
    side-effect the official grid order is cached for ``get_last_qualifying_grid``.

    ``expected_round`` closes the wrong-event class of failure (2026-07-05
    British-GP incident, commit ``09d607f``): FastF1's fuzzy event matcher can
    silently resolve one GP's name to a *different, already-run* event and hand
    back that event's qualifying. When ``expected_round`` is supplied, the
    resolved FastF1 session's ``RoundNumber`` must match it or the FastF1 result
    is rejected outright (falling through to the round-scoped Jolpica endpoint,
    which is inherently round-safe). This guarantees a wrong-event grid can never
    be promoted to ``real-quali-verified`` provenance.
    """
    override = _QUALI_TIMES_OVERRIDE.get(f"{int(year)}:{grand_prix}")
    if override:
        print("🏁 Using INJECTED official qualifying data (regeneration override).")
        return dict(override)

    from datetime import date as _date, timedelta as _timedelta
    for info in CALENDAR.values():
        if grand_prix.lower() in info["name"].lower() or \
           grand_prix.lower() == info.get("gp_key", "").lower():
            # Qualifying sets the grid the day before the race (Saturday) in both
            # normal and sprint formats. Skip only when qualifying day itself has
            # not arrived yet — keying off the race date instead would force a
            # Saturday post-quali run onto estimated times even though the real
            # grid is already published.
            quali_date = _date.fromisoformat(info["date"]) - _timedelta(days=1)
            if _date.today() < quali_date:
                print(f"📅 Qualifying day ({quali_date}) hasn't arrived — "
                      "skipping qualifying fetch.")
                return None
            break

    try:
        historical_gp = resolve_historical_gp_key(grand_prix)
        alias_note = f" via {historical_gp}" if historical_gp != grand_prix else ""
        print(f"🔍 Attempting to fetch {year} {grand_prix} qualifying{alias_note} …")
        import concurrent.futures
        def _load():
            s = fastf1.get_session(year, historical_gp, "Q")
            s.load(laps=True, telemetry=False, weather=False, messages=False)
            return s
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            session = ex.submit(_load).result(timeout=15)
        # Round-verification guard: reject a fuzzy-matched wrong event before
        # trusting a single lap of its data. Jolpica (round-scoped URL) is the
        # safe fallback.
        if expected_round is not None and not _fastf1_session_matches_round(session, expected_round):
            resolved = None
            try:
                resolved = session.event.get("RoundNumber")
            except Exception:
                resolved = "?"
            print(f"🛑 FastF1 resolved {grand_prix} qualifying to round {resolved}, "
                  f"expected round {expected_round} — rejecting wrong-event data, "
                  "trying Jolpica fallback…")
            return _fetch_qualifying_from_jolpica(year, grand_prix, expected_round=expected_round)
        laps = session.laps.copy()
        laps["Q (s)"] = laps["LapTime"].dt.total_seconds()
        best = laps.groupby("Driver")["Q (s)"].min().to_dict()
        # Drop drivers whose best lap is NaN (deleted/invalidated laps) — they
        # did not set a representative time and must NOT be promoted.
        best = {d: float(t) for d, t in best.items()
                if t is not None and not (isinstance(t, float) and np.isnan(t))}
        # Cache official grid (incl. no-time drivers at the back) for the
        # export pipeline's conservative seating.
        _QUALI_GRID_CACHE[f"{year}:{grand_prix}"] = _extract_qualifying_grid(session)
        if best:
            print(f"✅ Qualifying data fetched — {len(best)} drivers with valid laps.")
            return best
        print("ℹ️  FastF1 returned no timed laps — trying Jolpica fallback…")
        return _fetch_qualifying_from_jolpica(year, grand_prix, expected_round=expected_round)
    except Exception as exc:
        print(f"⚠️  FastF1 qualifying unavailable: {type(exc).__name__} — "
              "trying Jolpica fallback…")
        return _fetch_qualifying_from_jolpica(year, grand_prix, expected_round=expected_round)


# Seconds inserted between consecutive no-time drivers when seating them
# behind the field.  Large enough that QualifyingRank cleanly places them last.
QUALI_FLOOR_GAP_S = 0.75


def _timed_drivers(qualifying_times):
    """Set of drivers with a genuine (non-NaN) qualifying time."""
    if not qualifying_times:
        return set()
    out = set()
    for drv, t in qualifying_times.items():
        if t is None:
            continue
        if isinstance(t, float) and np.isnan(t):
            continue
        out.add(drv)
    return out


def apply_qualifying_data(merged, qualifying_times,
                          rain_probability=0.0, temperature_c=25.0,
                          fallback_times=None, grid_positions=None,
                          enforce_grid_floor=True):
    """Add qualifying + weather columns to the dataset.

    PRIORITY-1 RELIABILITY FIX (qualifying-NaN edge case):
    A driver who set **no valid qualifying time** (DNS, deleted laps, missing
    telemetry, incomplete session) must never be promoted ahead of drivers who
    did set a time.  When real qualifying is present but partial, no-time
    drivers are seated *behind the entire timed field* — ordered by official
    grid (``grid_positions``) when available, otherwise by their fallback
    estimate.  This is skipped when qualifying is fully synthetic (preview
    phase: every driver "missing") or fully present (no missing drivers), so
    pre-qualifying previews are unaffected.
    """
    merged = merged.copy()
    merged["QualifyingTime"] = merged["Driver"].map(qualifying_times)

    # Drivers that genuinely set a time *before* any fallback fills NaNs.
    timed = _timed_drivers(qualifying_times)
    no_time_mask = ~merged["Driver"].isin(timed)
    n_timed = int((~no_time_mask).sum())
    n_total = len(merged)
    # Conservative seating only applies to a *partial* real session: some
    # drivers timed, some not.  Fully-synthetic previews (n_timed == 0) and
    # complete sessions (n_timed == n_total) are no-ops.
    apply_floor = bool(enforce_grid_floor and 0 < n_timed < n_total)

    # FastF1 qualifying feeds can miss drivers (e.g., DNS/early retirement).
    # Backfill with generated estimates first, then with robust medians.
    missing_quali = merged["QualifyingTime"].isna()
    if missing_quali.any() and fallback_times:
        merged.loc[missing_quali, "QualifyingTime"] = (
            merged.loc[missing_quali, "Driver"].map(fallback_times)
        )
        missing_quali = merged["QualifyingTime"].isna()

    if missing_quali.any():
        clean_air_fallback = merged.loc[missing_quali, "CleanAirPace"]
        merged.loc[missing_quali, "QualifyingTime"] = clean_air_fallback

    if merged["QualifyingTime"].isna().any():
        global_fallback = float(merged["QualifyingTime"].dropna().median())
        if np.isnan(global_fallback):
            global_fallback = float(merged["CleanAirPace"].median())
        merged["QualifyingTime"] = merged["QualifyingTime"].fillna(global_fallback)

    if rain_probability >= 0.75:
        merged["AdjustedQualiTime"] = (
            merged["QualifyingTime"] * merged["WetPerformance"]
        )
        print("🌧️  Wet qualifying adjustment applied.")
    else:
        merged["AdjustedQualiTime"] = merged["QualifyingTime"]
        print("☀️  Dry conditions — raw qualifying times used.")
    merged["RainProbability"] = rain_probability
    merged["Temperature"]     = temperature_c
    merged["WeatherRiskScore"] = (
        rain_probability * 0.65 + max(0.0, abs(temperature_c - 24.0) / 20.0) * 0.35
    )

    if merged["AdjustedQualiTime"].isna().any():
        merged["AdjustedQualiTime"] = merged["AdjustedQualiTime"].fillna(
            merged["QualifyingTime"]
        )

    # ── Conservative back-of-grid seating for no-time drivers ──
    merged["QualifyingDataMissing"] = no_time_mask.values
    if apply_floor:
        slowest_timed = float(merged.loc[~no_time_mask, "AdjustedQualiTime"].max())
        no_time_drivers = list(merged.loc[no_time_mask, "Driver"])
        if grid_positions:
            order_key = {d: grid_positions.get(d, 10_000 + i)
                         for i, d in enumerate(no_time_drivers)}
        else:
            est = merged.set_index("Driver")["AdjustedQualiTime"].to_dict()
            order_key = {d: est.get(d, float("inf")) for d in no_time_drivers}
        for rank, drv in enumerate(sorted(no_time_drivers, key=lambda d: order_key[d]), start=1):
            penalised = slowest_timed + QUALI_FLOOR_GAP_S * rank
            merged.loc[merged["Driver"] == drv, "AdjustedQualiTime"] = penalised
            merged.loc[merged["Driver"] == drv, "QualifyingTime"] = penalised
        print(f"🛑 Conservative grid floor applied to {len(no_time_drivers)} "
              f"no-time driver(s): {sorted(no_time_drivers)} (seated behind P{n_timed}).")

    merged["QualifyingRank"] = merged["AdjustedQualiTime"].rank(method="min")
    median_quali = merged["AdjustedQualiTime"].median()
    merged["GridAdvantage"] = median_quali - merged["AdjustedQualiTime"]
    print(f"✅ Qualifying data added for {n_timed}/{n_total} drivers with valid laps.")
    return merged


def _zscore(series):
    values = pd.Series(series, dtype=float)
    std = values.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - values.mean()) / std


def _env_float(name, default, min_value=None, max_value=None):
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        value = float(default)
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = float(default)

    if min_value is not None:
        value = max(float(min_value), value)
    if max_value is not None:
        value = min(float(max_value), value)
    return value


def circuit_grid_dynamics(overtaking, safety_car, rain_probability=0.0):
    """Circuit-conditioned weighting of grid position in the race outcome.

    The single biggest reason a flat win probability is wrong is that it ignores
    *track position*. On circuits where overtaking is hard (Monaco,
    ``overtaking≈0.1``) the starting grid is the dominant predictor of the
    result — the pole-sitter has by far the best chance of winning and the
    order barely changes. On open circuits (Monza/Bahrain, ``overtaking≈0.7+``)
    race pace routinely overrides grid, so the grid prior is light and the win
    chance is spread across the front of the field. Safety cars and rain
    scramble the order, softening the lock either way.

    This runs for **every** round — the circuit's ``overtaking`` characteristic
    is what makes Monaco behave differently from Monza, automatically.

    Returns:
        pole_lock   – weight applied to the grid-rank z-score when building the
                      race-projection score (higher → grid order dominates the
                      predicted finishing order).
        win_decay_k – decay length, in finishing positions, of the win
                      probability. Small → a confident, pole-dominant favourite;
                      large → win chance spread across the field.
    """
    overtaking = float(np.clip(overtaking, 0.0, 1.0))
    safety_car = float(np.clip(safety_car, 0.0, 1.0))
    rain = float(np.clip(rain_probability, 0.0, 1.0))

    # How "locked" the grid is: hard to pass, dry, low safety-car risk.
    stickiness = float(np.clip(
        (1.0 - overtaking) * (1.0 - 0.30 * safety_car) * (1.0 - 0.45 * rain),
        0.0, 1.0,
    ))
    pole_lock = 0.95 * stickiness

    # How "open" the race is: easy to pass, wet, safety-car prone. Drives how
    # quickly win probability decays from the projected leader down the order.
    openness = float(np.clip(
        0.22 + 0.78 * overtaking + 0.30 * rain + 0.12 * safety_car,
        0.18, 1.20,
    ))
    win_decay_k = float(np.clip(1.5 + 5.5 * openness, 1.5, 8.0))
    return pole_lock, win_decay_k


def apply_race_postprocessing(merged, circuit_key="Australia", rain_probability=0.0):
    """Transform baseline lap-time predictions into more realistic race outcomes."""
    char = CIRCUIT_CHARACTERISTICS.get(circuit_key, {})
    overtaking = char.get("overtaking", 0.5)
    safety_car = char.get("safety_car_likelihood", 0.4)
    tyre_deg = char.get("tyre_deg", 0.5)

    quali_lock_in = np.clip(
        0.58 + 0.34 * (1.0 - overtaking) + 0.12 * (1.0 - safety_car) - 0.18 * rain_probability,
        0.28,
        0.82,
    )
    pace_weight = np.clip(
        0.52 + 0.24 * overtaking + 0.10 * tyre_deg + 0.15 * rain_probability,
        0.38,
        0.84,
    )
    form_weight = 0.16 + 0.04 * rain_probability
    consistency_weight = 0.10 + 0.04 * tyre_deg
    strategy_weight = 0.08 + 0.04 * overtaking

    weight_total = quali_lock_in + pace_weight + form_weight + consistency_weight + strategy_weight
    quali_lock_in /= weight_total
    pace_weight /= weight_total
    form_weight /= weight_total
    consistency_weight /= weight_total
    strategy_weight /= weight_total

    # Optional runtime tuning knobs for game-theory postprocessing influence.
    # Default was calibrated with optimize_game_theory_postprocessing.py on completed rounds 1-3.
    game_theory_scale = _env_float("F1_GAME_THEORY_POSTPROCESS_SCALE", 1.2, 0.0, 2.5)
    uncertainty_scale = _env_float(
        "F1_GAME_THEORY_UNCERTAINTY_SCALE",
        game_theory_scale,
        0.0,
        2.5,
    )

    merged = merged.copy()
    driver_bias_term = (
        _zscore(merged["DriverPredictionBias"])
        if "DriverPredictionBias" in merged.columns
        else 0.0
    )
    team_bias_term = (
        _zscore(merged["TeamPredictionBias"])
        if "TeamPredictionBias" in merged.columns
        else 0.0
    )
    team_form_term = (
        _zscore(merged["TeamFormDelta"])
        if "TeamFormDelta" in merged.columns
        else 0.0
    )
    undercut_term = (
        _zscore(merged["UndercutEdgeAhead"])
        if "UndercutEdgeAhead" in merged.columns
        else 0.0
    )
    overcut_term = (
        _zscore(merged["OvercutEdgeBehind"])
        if "OvercutEdgeBehind" in merged.columns
        else 0.0
    )
    team_order_term = (
        _zscore(merged["TeamOrderPressure"])
        if "TeamOrderPressure" in merged.columns
        else 0.0
    )
    teammate_conflict_term = (
        _zscore(merged["TeammateConflictRisk"])
        if "TeammateConflictRisk" in merged.columns
        else 0.0
    )
    drs_term = (
        _zscore(merged["DRSOvertakeProbAhead"])
        if "DRSOvertakeProbAhead" in merged.columns
        else 0.0
    )
    battle_term = (
        _zscore(merged["LocalBattleIntensity"])
        if "LocalBattleIntensity" in merged.columns
        else 0.0
    )
    field_volatility_term = (
        _zscore(merged["FieldPositionVolatility"])
        if "FieldPositionVolatility" in merged.columns
        else 0.0
    )

    merged["RaceProjectionScore"] = (
        _zscore(merged["PredictedLapTime"]) * pace_weight +
        _zscore(merged["AdjustedQualiTime"]) * quali_lock_in +
        _zscore(merged["CleanAirPace"]) * (pace_weight * 0.55) +
        _zscore(merged["CurrentForm"]) * form_weight +
        _zscore(merged["PreviousPosition"]) * (form_weight * 0.45) +
        _zscore(merged["ConsistencyScore"]) * consistency_weight +
        _zscore(merged["PitTimeLoss"]) * strategy_weight +
        _zscore(merged["TyreDegFactor"]) * (strategy_weight * 0.55) -
        undercut_term * (strategy_weight * 0.30 * game_theory_scale) -
        overcut_term * (strategy_weight * 0.22 * game_theory_scale) -
        team_order_term * (0.035 * game_theory_scale) +
        drs_term * (-0.04 * game_theory_scale) +
        battle_term * (0.025 * game_theory_scale) +
        _zscore(merged["SeasonMomentum"]) * 0.05 +
        _zscore(merged["GridAdvantage"]) * -0.08 -
        driver_bias_term * 0.07 -
        team_bias_term * 0.05 -
        team_form_term * 0.04 +
        teammate_conflict_term * (0.022 * game_theory_scale) +
        field_volatility_term * (0.028 * game_theory_scale)
    )

    # Circuit-conditioned grid-position prior. The terms above rank drivers
    # mostly on pace; on hard-to-pass circuits that under-weights the simple
    # fact that you can't win a race you can't overtake your way to the front
    # of. ``pole_lock`` pulls the predicted order toward the starting grid in
    # proportion to how grid-locked the track is (strong at Monaco, light at
    # Monza), so the pole-sitter is favoured by default and the win-probability
    # decay below stays consistent with the finishing order.
    pole_lock, win_decay_k = circuit_grid_dynamics(
        overtaking, safety_car, rain_probability
    )
    grid_rank = merged["QualifyingRank"].fillna(merged["QualifyingRank"].max())
    merged["RaceProjectionScore"] = (
        merged["RaceProjectionScore"] + _zscore(grid_rank) * pole_lock
    )

    merged["RaceProjectionTime"] = (
        merged["PredictedLapTime"].min() + 1.15 + _zscore(merged["RaceProjectionScore"]) * 0.85
    )

    model_cols = ["PredictedLapTime_GB", "PredictedLapTime_XGB"]
    if "PredictedLapTime_LSTM" in merged.columns:
        model_cols.append("PredictedLapTime_LSTM")
    model_dispersion = merged[model_cols].std(axis=1).fillna(0.0)

    volatility = 0.55 * (1.0 - overtaking) + 0.25 * rain_probability + 0.20 * safety_car
    raw_uncertainty = (
        model_dispersion +
        merged["ConsistencyScore"].fillna(0.0) * 18.0 +
        np.abs(merged["PositionTrend"]).fillna(0.0) * 0.18 +
        np.abs(merged.get("DriverPredictionBias", 0.0)) * 0.06 +
        np.abs(merged.get("TeamPredictionBias", 0.0)) * 0.08 +
        np.abs(merged.get("FieldPositionVolatility", 0.0)) * (0.10 * uncertainty_scale) +
        np.abs(merged.get("LocalBattleIntensity", 0.0)) * (0.15 * uncertainty_scale) +
        np.abs(merged.get("TeammateConflictRisk", 0.0)) * (0.08 * uncertainty_scale) +
        volatility
    )
    uncertainty_floor = max(float(np.nanpercentile(raw_uncertainty, 20)), 0.45)
    uncertainty_ceiling = max(float(np.nanpercentile(raw_uncertainty, 85)), uncertainty_floor + 0.25)
    merged["PredictionUncertainty"] = raw_uncertainty.round(3)
    merged["UncertaintyPercentile"] = (
        (raw_uncertainty - uncertainty_floor) / (uncertainty_ceiling - uncertainty_floor)
    ).clip(0.0, 1.0)
    merged["PredictionConfidence"] = pd.cut(
        merged["UncertaintyPercentile"],
        bins=[-np.inf, 0.34, 0.68, np.inf],
        labels=["High", "Medium", "Low"],
    ).astype(str)

    # Split-conformal prediction intervals from the accumulated
    # residual cache. Additive — the legacy PredictionConfidence
    # column stays as-is; the new fields expose a *statistically
    # valid* interval that the website + forward-eval can audit
    # against observed coverage.
    try:
        from models.conformal import (
            ConformalIntervals,
            MIN_CALIBRATION_SAMPLES,
            load_residual_history,
            width_to_confidence_label,
        )

        cur_season = int(os.getenv("F1_SEASON_YEAR", SEASON_YEAR))
        cur_round = int(os.getenv("F1_CURRENT_ROUND", "0") or 0)
        if cur_round > 0:
            residuals = load_residual_history(
                current_season=cur_season,
                current_round=cur_round,
                max_seasons_back=1,
            )
            if residuals.size >= MIN_CALIBRATION_SAMPLES:
                # Treat the residuals as one-sided absolute values
                # already; ConformalIntervals expects ``(y, yhat)`` so
                # we synthesise a paired (0, residual) calibration set
                # with the same quantile by construction.
                cal_y = residuals
                cal_yhat = np.zeros_like(residuals)
                conf = ConformalIntervals(alpha=0.10).fit(cal_y, cal_yhat)
                pred = merged["PredictedLapTime"].to_numpy(dtype=np.float64)
                lows, highs = conf.predict_intervals(pred)
                widths = highs - lows
                merged["PredictedLapTimeConformalLow"] = lows
                merged["PredictedLapTimeConformalHigh"] = highs
                merged["ConformalIntervalWidth"] = widths
                merged["CalibratedConfidence"] = width_to_confidence_label(widths)
                print(
                    f"✅ Conformal intervals applied "
                    f"(n_calibration={residuals.size}, q90={conf.quantile:.3f}s)."
                )
            else:
                print(
                    f"ℹ️  Conformal calibration deferred — need >= "
                    f"{MIN_CALIBRATION_SAMPLES} residuals, got {residuals.size}."
                )
    except Exception as exc:  # noqa: BLE001 — non-blocking
        print(f"⚠️  Conformal intervals skipped: {exc}")

    # Learned race-projection head (opt-in via registry). If a head has
    # been trained for the current season and saved to sentinel round 96,
    # load it and emit a shadow ``RaceProjectionScoreLearned`` column. If
    # ``F1_USE_LEARNED_HEAD=1``, the learned column also replaces the
    # legacy ``RaceProjectionScore`` field for downstream consumers.
    try:
        from models.race_projection_head import DEFAULT_HEAD_FEATURES
        from models.registry import ModelRegistry

        cur_season = int(os.getenv("F1_SEASON_YEAR", SEASON_YEAR))
        registry = ModelRegistry()
        loaded = registry.load(cur_season, 96)
        head = loaded.get("race_projection_head") if loaded else None
        if head is not None and head.is_fitted:
            cols_present = [c for c in DEFAULT_HEAD_FEATURES if c in merged.columns]
            if len(cols_present) == len(DEFAULT_HEAD_FEATURES):
                feature_matrix = merged[list(DEFAULT_HEAD_FEATURES)].to_numpy(
                    dtype=np.float64, na_value=0.0
                )
                raw = head.predict(feature_matrix)
                centred = (raw - raw.mean()) / (raw.std() or 1.0)
                merged["RaceProjectionScoreLearned"] = centred
                if os.getenv("F1_USE_LEARNED_HEAD") == "1":
                    merged["RaceProjectionScore"] = centred
                    print(
                        "✅ Learned race-projection head active "
                        "(F1_USE_LEARNED_HEAD=1)."
                    )
                else:
                    print(
                        "ℹ️  Learned head loaded as shadow column "
                        "RaceProjectionScoreLearned (legacy is load-bearing)."
                    )
            else:
                missing = set(DEFAULT_HEAD_FEATURES) - set(cols_present)
                print(
                    f"ℹ️  Learned head feature columns missing: {missing}; "
                    "skipping shadow score."
                )
    except Exception as exc:  # noqa: BLE001 — non-blocking
        print(f"ℹ️  Learned head shadow score skipped: {exc}")

    # Win probability decays from the projected leader down the finishing order,
    # so the predicted winner (P1) always holds the highest win chance — the
    # finishing order and the win odds can no longer disagree. ``win_decay_k``
    # sets how sharply: small on grid-locked tracks (a dominant pole-sitter),
    # large on open tracks (a wide-open front). A secondary pace-gap term lets a
    # genuinely dominant car pull further clear than rank alone would imply.
    order_rank = merged["RaceProjectionTime"].rank(method="first")
    proj_z = _zscore(merged["RaceProjectionScore"])
    score_gap = (proj_z - proj_z.min()).clip(lower=0.0)
    win_weights = np.exp(-(order_rank - 1.0) / win_decay_k) * np.exp(-0.30 * score_gap)
    merged["WinProbability"] = (win_weights / max(win_weights.sum(), 1e-9) * 100).round(1)
    print(
        f"✅ Race-aware postprocessing applied "
        f"(quali={quali_lock_in:.0%}, pace={pace_weight:.0%}, form={form_weight:.0%}, "
        f"pole-lock={pole_lock:.2f}, win-k={win_decay_k:.1f}, gt-scale={game_theory_scale:.2f})."
    )
    return merged


def get_qualifying_or_estimates(year, grand_prix, estimates, expected_round=None):
    """Auto-fetch qualifying or fall back to estimates.

    ``expected_round`` is forwarded to :func:`fetch_qualifying_data` so a
    wrong-event grid is rejected at the source and the caller falls back to
    (honestly labelled) estimates rather than a mislabelled real grid.
    """
    actual = fetch_qualifying_data(year, grand_prix, expected_round=expected_round)
    if actual is not None:
        print("🏁 Using ACTUAL qualifying data.")
        return actual
    print("📝 Using ESTIMATED qualifying times.")
    return estimates


def generate_qualifying_estimates(circuit_key):
    """Auto-generate reasonable qualifying estimates for any circuit.

    Uses base_quali_s × (1 + DRIVER_QUALI_OFFSET[driver]).
    """
    char = CIRCUIT_CHARACTERISTICS.get(circuit_key, {})
    base = char.get("base_quali_s", 80.0)
    return {drv: round(base * (1 + off), 2)
            for drv, off in DRIVER_QUALI_OFFSET.items()}


# ==========================================================================
# 6. MODEL TRAINING  (v2 — StandardScaler + calibration)
# ==========================================================================

def _load_hps_config(path: str = "models/hps_config.json") -> dict:
    """Load Optuna-tuned hyperparameters from disk; return {} if absent."""
    try:
        if not os.path.exists(path):
            return {}
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def train_ensemble(merged, feature_cols=None, target_col="AdjustedQualiTime",
                   test_size=0.2, random_state=42, calibrate=True,
                   max_spread_s=3.5, gb_params=None, xgb_params=None,
                   lstm_predictions=None, lstm_weight=0.20,
                   sample_weight=None):
    """Train Gradient Boosting + XGBoost + optional LSTM ensemble.

    v3 improvements:
      - **StandardScaler** on features → no single feature dominates
      - **Prediction calibration** → compress spread to realistic F1 gaps
      - **LSTM integration** → if lstm_predictions provided, 3-model
        weighted ensemble: GBR (0.40) + XGB (0.40) + LSTM (0.20)
        Falls back to GBR/XGB 50/50 if LSTM unavailable.
      - **Time-decay sample weighting** → if ``sample_weight`` is provided,
        recent training rows weigh more than old ones via
        :func:`models.time_decay.compute_sample_weights`. Default
        ``sample_weight=None`` preserves the legacy uniform fit.

    Parameters
    ----------
    lstm_predictions : np.ndarray | None
        Predicted qualifying times from the LSTM for each driver (22 values).
        Must be aligned with merged DataFrame rows.
    lstm_weight : float
        Weight for LSTM in the ensemble (default 0.20). GBR and XGB
        split the remaining weight equally.
    sample_weight : array-like | None
        Per-row sample weight (aligned with ``merged``). Forwarded to
        both GBR and XGB ``.fit(...)`` calls. When ``None`` (default),
        all rows weigh equally — backward compatible with prior callers.
    """
    if feature_cols is None:
        feature_cols = DEFAULT_FEATURE_COLS

    # Use only columns that actually exist in merged
    available = [c for c in feature_cols if c in merged.columns]
    if len(available) < len(feature_cols):
        missing = set(feature_cols) - set(available)
        print(f"⚠️  Features not found, skipping: {missing}")
        feature_cols = available

    X = merged[feature_cols].copy()
    y = merged[target_col].copy()

    # Impute
    imp_X = SimpleImputer(strategy="median")
    X_imp = pd.DataFrame(imp_X.fit_transform(X), columns=feature_cols)
    imp_y = SimpleImputer(strategy="median")
    y_imp = imp_y.fit_transform(y.values.reshape(-1, 1)).ravel()

    # **Scale features** (v2 key fix)
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X_imp), columns=feature_cols)

    print(f"Feature matrix : {X_scaled.shape}")
    print(f"Target vector  : {y_imp.shape}")

    if sample_weight is not None:
        sw = np.asarray(sample_weight, dtype=np.float64)
        if sw.shape[0] != len(merged):
            raise ValueError(
                f"sample_weight length {sw.shape[0]} != merged length "
                f"{len(merged)}; the weight vector must be row-aligned."
            )
        X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
            X_scaled, y_imp, sw,
            test_size=test_size, random_state=random_state,
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_imp, test_size=test_size, random_state=random_state,
        )
        w_train = None

    # Determine if LSTM is part of the ensemble
    use_lstm = (lstm_predictions is not None
                and len(lstm_predictions) == len(merged))
    if use_lstm:
        w_lstm = lstm_weight
        w_gb   = (1.0 - w_lstm) / 2
        w_xgb  = (1.0 - w_lstm) / 2
        total_steps = 4
        print("🧠 LSTM integrated into ensemble candidate pool.")
    else:
        w_gb  = 0.5
        w_xgb = 0.5
        total_steps = 3
        if lstm_predictions is not None:
            print(f"⚠️  LSTM predictions length mismatch "
                  f"({len(lstm_predictions)} vs {len(merged)}), using GBR+XGB only")

    pbar = tqdm(total=total_steps, desc="Training models", unit="step")

    # Gradient Boosting
    pbar.set_postfix(model="Gradient Boosting")
    _hps = _load_hps_config()
    _gb = gb_params or {**dict(n_estimators=200, learning_rate=0.05,
                                max_depth=3, random_state=random_state),
                         **(_hps.get("gb") or {})}
    gb_model = GradientBoostingRegressor(**_gb)
    gb_model.fit(X_train, y_train, sample_weight=w_train)
    pbar.update(1)

    # XGBoost
    pbar.set_postfix(model="XGBoost")
    _xgb = xgb_params or {**dict(n_estimators=250, learning_rate=0.05,
                                  max_depth=3, random_state=random_state,
                                  verbosity=0),
                           **(_hps.get("xgb") or {})}
    xgb_model = XGBRegressor(**_xgb)
    xgb_model.fit(X_train, y_train, sample_weight=w_train)
    pbar.update(1)

    gb_test = gb_model.predict(X_test)
    xgb_test = xgb_model.predict(X_test)
    gb_mae = mean_absolute_error(y_test, gb_test)
    xgb_mae = mean_absolute_error(y_test, xgb_test)
    inv_gb = 1.0 / max(gb_mae, 1e-6)
    inv_xgb = 1.0 / max(xgb_mae, 1e-6)
    if use_lstm:
        base_total = inv_gb + inv_xgb
        gb_share = inv_gb / base_total
        xgb_share = inv_xgb / base_total
        w_lstm = min(max(lstm_weight, 0.10), 0.18)
        w_gb = (1.0 - w_lstm) * gb_share
        w_xgb = (1.0 - w_lstm) * xgb_share
    else:
        total_inv = inv_gb + inv_xgb
        w_gb = inv_gb / total_inv
        w_xgb = inv_xgb / total_inv

    # LSTM predictions (pre-computed, just validate & align)
    lstm_all = None
    if use_lstm:
        pbar.set_postfix(model="LSTM (pre-trained)")
        lstm_all = np.array(lstm_predictions, dtype=float)
        pbar.update(1)

    # Ensemble predictions
    pbar.set_postfix(model="Ensemble")
    gb_all  = gb_model.predict(X_scaled)
    xgb_all = xgb_model.predict(X_scaled)

    if use_lstm and lstm_all is not None:
        ensemble = w_gb * gb_all + w_xgb * xgb_all + w_lstm * lstm_all
    else:
        ensemble = w_gb * gb_all + w_xgb * xgb_all

    # **Calibrate** — compress spread to realistic F1 range
    if calibrate:
        raw_spread = ensemble.max() - ensemble.min()
        if raw_spread > max_spread_s and raw_spread > 0:
            min_pred = ensemble.min()
            scale = max_spread_s / raw_spread
            gb_all   = min_pred + (gb_all - min_pred) * scale
            xgb_all  = min_pred + (xgb_all - min_pred) * scale
            if lstm_all is not None:
                lstm_all = min_pred + (lstm_all - min_pred) * scale
            ensemble = min_pred + (ensemble - min_pred) * scale
            print(f"📏 Calibrated: {raw_spread:.1f}s → {max_spread_s}s spread.")

    merged = merged.copy()
    merged["PredictedLapTime_GB"]  = gb_all
    merged["PredictedLapTime_XGB"] = xgb_all
    if lstm_all is not None:
        merged["PredictedLapTime_LSTM"] = lstm_all
    merged["PredictedLapTime"]     = ensemble
    pbar.update(1)
    pbar.close()

    # A-P2.3: bootstrap-based 90% prediction intervals on the quali-time
    # ensemble.  Best-effort; failures are non-fatal so the legacy point
    # estimate keeps shipping.  After bootstrap we clip the band to the
    # final ensemble's spread so the interval can't be wider than the
    # post-calibration display range.
    try:
        from models.intervals import bootstrap_prediction_intervals
        low_pred, high_pred = bootstrap_prediction_intervals(
            X_train.to_numpy(), y_train,
            X_scaled.to_numpy(),
            n_replicas=20, n_estimators=80, random_state=random_state,
        )
        # Re-anchor the interval to the post-calibration ensemble so it
        # tracks the rendered times.  Median of replicas ≈ ensemble; any
        # post-cal compression is then proportional.
        if calibrate:
            ensemble_min = ensemble.min()
            ensemble_max = ensemble.max()
            ensemble_spread = max(ensemble_max - ensemble_min, 1e-6)
            replica_median_spread = max(
                np.median(high_pred - low_pred), 1e-6
            )
            shrink = min(1.0, ensemble_spread / replica_median_spread)
            low_pred = ensemble - (ensemble - low_pred) * shrink
            high_pred = ensemble + (high_pred - ensemble) * shrink
        merged["PredictedLapTimeLow"] = low_pred
        merged["PredictedLapTimeHigh"] = high_pred
    except Exception as exc:  # noqa: BLE001 — never block the pipeline on intervals
        print(f"⚠️  Bootstrap prediction intervals skipped: {exc}")

    ensemble_desc = "GBR+XGB+LSTM" if use_lstm else "GBR+XGB"
    print(f"⚖️  Dynamic ensemble weights: GBR={w_gb:.0%}, XGB={w_xgb:.0%}"
          + (f", LSTM={w_lstm:.0%}" if use_lstm else ""))

    # Ensemble's prediction on the held-out test split — the source
    # of conformal calibration residuals. Best-effort persistence so
    # the next round's apply_race_postprocessing can fit a tight
    # split-conformal interval from the accumulated cache.
    try:
        from models.conformal import save_round_residuals

        ensemble_test = w_gb * gb_test + w_xgb * xgb_test
        if use_lstm and lstm_predictions is not None:
            # LSTM predictions are full-population; project onto X_test via the
            # same row indices the splitter chose. We didn't keep the indices
            # explicitly; the legacy code blends LSTM only at inference time.
            # Skip LSTM blending for the calibration residuals — it would
            # only matter if the LSTM materially shifts the ensemble's
            # held-out residual distribution, which we measure-then-fix
            # in forward_eval rather than mask here.
            pass
        residuals = ensemble_test - y_test
        cur_season = int(os.getenv("F1_SEASON_YEAR", SEASON_YEAR))
        cur_round = int(os.getenv("F1_CURRENT_ROUND", "0") or 0)
        if cur_round > 0:
            save_round_residuals(cur_season, cur_round, residuals)
    except Exception as exc:  # noqa: BLE001 - calibration cache is non-blocking
        print(f"⚠️  Conformal residual cache skipped: {exc}")

    print(f"✅ Ensemble model trained successfully ({ensemble_desc}).")
    return {
        "gb_model": gb_model, "xgb_model": xgb_model,
        "lstm_used": use_lstm, "lstm_predictions": lstm_all,
        "X_imputed": X_imp, "X_scaled": X_scaled,
        "y_imputed": y_imp, "scaler": scaler,
        "X_test": X_test, "y_test": y_test,
        "ensemble_weights": {"gb": w_gb, "xgb": w_xgb, "lstm": w_lstm if use_lstm else 0.0},
        "test_predictions": {"gb": gb_test, "xgb": xgb_test},
        "merged": merged, "feature_cols": feature_cols,
    }


def evaluate_models(results):
    """Evaluate GB, XGB, optional LSTM, and ensemble on held-out test set."""
    X_test, y_test = results["X_test"], results["y_test"]
    rows = []
    for name, model in [("Gradient Boosting", results["gb_model"]),
                         ("XGBoost", results["xgb_model"])]:
        yp  = model.predict(X_test)
        rows.append({"Model": name,
                      "MAE (s)": mean_absolute_error(y_test, yp),
                      "RMSE (s)": np.sqrt(mean_squared_error(y_test, yp)),
                      "R²": r2_score(y_test, yp)})

    # LSTM component (if used)
    lstm_used = results.get("lstm_used", False)
    if lstm_used:
        rows.append({"Model": "LSTM Neural Network",
                      "MAE (s)": 0.0,  # LSTM doesn't have test split
                      "RMSE (s)": 0.0,
                      "R²": 0.0})

    # Ensemble
    gb_test  = results.get("test_predictions", {}).get("gb")
    xgb_test = results.get("test_predictions", {}).get("xgb")
    if gb_test is None:
        gb_test = results["gb_model"].predict(X_test)
    if xgb_test is None:
        xgb_test = results["xgb_model"].predict(X_test)
    weights = results.get("ensemble_weights", {"gb": 0.5, "xgb": 0.5, "lstm": 0.0})
    if lstm_used:
        # LSTM does not expose a held-out test split in this implementation,
        # so evaluation uses the calibrated GBR/XGB blend.
        eval_weight_sum = max(weights["gb"] + weights["xgb"], 1e-9)
        ens = (
            (weights["gb"] / eval_weight_sum) * gb_test +
            (weights["xgb"] / eval_weight_sum) * xgb_test
        )
        ens_name = "Ensemble (GBR + XGB + LSTM)"
    else:
        ens = weights["gb"] * gb_test + weights["xgb"] * xgb_test
        ens_name = "Ensemble (GBR + XGB)"

    rows.append({"Model": ens_name,
                  "MAE (s)": mean_absolute_error(y_test, ens),
                  "RMSE (s)": np.sqrt(mean_squared_error(y_test, ens)),
                  "R²": r2_score(y_test, ens)})
    metrics = pd.DataFrame(rows)
    print("📊 Model Evaluation (Test Set)")
    print("=" * 65)
    for _, r in metrics.iterrows():
        print(f"  {r['Model']:30s}  MAE: {r['MAE (s)']:.3f}s | "
              f"RMSE: {r['RMSE (s)']:.3f}s | R²: {r['R²']:.3f}")
    print("=" * 65)
    return metrics


# ==========================================================================
# 7. RESULTS & DISPLAY
# ==========================================================================

def predicted_classification(merged, gp_name="Grand Prix"):
    """Sort by predicted lap time → finishing order with points."""
    results = (
        merged[["Driver", "DriverName", "Team", "QualifyingTime",
                "PredictedLapTime_GB", "PredictedLapTime_XGB",
                "PredictedLapTime", "RaceProjectionTime",
                "PredictionUncertainty", "PredictionConfidence",
                "WinProbability"]]
        .sort_values("RaceProjectionTime" if "RaceProjectionTime" in merged.columns else "PredictedLapTime")
        .reset_index(drop=True)
    )
    results.index += 1
    results.index.name = "Pos"
    results["Points"] = results.index.map(lambda p: F1_POINTS.get(p, 0))
    anchor_col = "RaceProjectionTime" if "RaceProjectionTime" in results.columns else "PredictedLapTime"
    results["Gap"]    = (results[anchor_col] - results[anchor_col].iloc[0]).round(3)
    if "UncertaintyPercentile" in merged.columns:
        results["UncertaintyPercentile"] = merged["UncertaintyPercentile"].values
        uncertainty_steps = (
            1 + np.clip(np.round(results["UncertaintyPercentile"].fillna(0.5) * 3), 0, 3)
        ).astype(int)
    else:
        uncertainty_steps = np.clip(np.ceil(results["PredictionUncertainty"].fillna(0.8)), 1, 4).astype(int)
    results["FinishRangeLow"] = np.maximum(1, results.index.to_series() - uncertainty_steps)
    results["FinishRangeHigh"] = np.minimum(len(results), results.index.to_series() + uncertainty_steps)

    print("\n" + "=" * 80)
    print(f"  🏁  PREDICTED {gp_name.upper()} FINISHING ORDER  🏁")
    print("=" * 80)
    for pos, row in results.iterrows():
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, "  ")
        gap   = "LEADER" if pos == 1 else f"+{row['Gap']:.3f}s"
        print(f"  {medal}{pos:>2}  {row['Driver']:<5} {row['DriverName']:<22} "
              f"{row['Team']:<18} {row[anchor_col]:.3f}s  "
              f"{gap:>10}  {row['Points']:>2} pts  "
              f"[{row['PredictionConfidence']}]")
    print("=" * 80)
    return results


# ==========================================================================
# 8. SEASON TRACKING
# ==========================================================================

def save_race_result(round_num, classification):
    """Persist actual race results so later rounds can use them as features.

    Call this AFTER a race with the actual finishing order.
    """
    data = _normalize_round_results(_read_json_file(SEASON_RESULTS_FILE))

    rnd = {row["Driver"]: int(pos) for pos, row in classification.iterrows()}
    data[str(round_num)] = rnd

    _write_json_file(SEASON_RESULTS_FILE, data)
    _write_json_file(SEASON_RESULTS_WEBSITE_FILE, data)
    print(f"💾 Round {round_num} actual results saved to {SEASON_RESULTS_FILE}.")


def save_predicted_result(round_num, classification):
    """Auto-persist predicted finishing order so next round can use it.

    v3 NEW — This is what makes the model truly scalable race-to-race.
    Called automatically after every prediction. The next round's
    CurrentForm, PreviousPosition, SeasonMomentum, and PositionTrend
    features all read from this file.

    Parameters
    ----------
    classification : pd.DataFrame
        The prediction result from predicted_classification(), with
        'Driver' column and positional index.
    """
    data = _normalize_round_results(_read_json_file(PREDICTED_RESULTS_FILE))
    # A freshly generated round invalidates older future forecasts, especially
    # after calendar changes or late-weekend data refreshes.
    data = {
        rnd: positions
        for rnd, positions in data.items()
        if int(rnd) < int(round_num)
    }

    rnd = {row["Driver"]: int(pos) for pos, row in classification.iterrows()}
    data[str(round_num)] = rnd

    _write_json_file(PREDICTED_RESULTS_FILE, data)
    _write_json_file(PREDICTED_RESULTS_WEBSITE_FILE, data)
    print(f"💾 Round {round_num} predicted results saved → {PREDICTED_RESULTS_FILE} "
          f"(feeds next round's features).")


# ==========================================================================
# 9. VISUALISATIONS
# ==========================================================================

def _safe_name(name):
    return name.replace(" ", "_").replace("—", "-").replace("/", "-")

def _viz_dir(gp_name, team=None):
    base = os.path.join("visualizations", _safe_name(gp_name))
    return os.path.join(base, _safe_name(team)) if team else base

def _save(fig, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    print(f"  💾 {path}")


def plot_feature_importance(results, gp_name="Grand Prix", save=True):
    feature_cols = results["feature_cols"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    for ax, model, title in zip(
        axes, [results["gb_model"], results["xgb_model"]],
        ["Gradient Boosting", "XGBoost"],
    ):
        imp = model.feature_importances_
        idx = np.argsort(imp)
        ax.barh(np.array(feature_cols)[idx], imp[idx], color="steelblue")
        ax.set_xlabel("Feature Importance")
        ax.set_title(f"{title} — Feature Importance")
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name), "feature_importance.png"))
    plt.close(fig)


def plot_predicted_laptimes(merged, gp_name="Grand Prix", save=True):
    fig, ax = plt.subplots(figsize=(12, 9))
    data = merged.sort_values("PredictedLapTime", ascending=True).copy()
    colours = data["Team"].map(TEAM_COLOURS).fillna("#888888")
    bars = ax.barh(data["Driver"], data["PredictedLapTime"],
                   color=colours, edgecolor="white")
    ax.set_xlabel("Predicted Avg Lap Time (s)")
    ax.set_title(f"🏁 {SEASON_YEAR} {gp_name} — Predicted Race Performance")
    ax.invert_yaxis()
    for bar, val in zip(bars, data["PredictedLapTime"]):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f"{val:.2f}s", va="center", fontsize=8)
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name), "predicted_laptimes.png"))
    plt.close(fig)


def plot_team_vs_pace(merged, gp_name="Grand Prix", save=True):
    fig, ax = plt.subplots(figsize=(12, 7))
    sc = ax.scatter(merged["TeamPerformanceScore"], merged["PredictedLapTime"],
                    c=merged["QualifyingTime"], cmap="RdYlGn_r",
                    s=120, edgecolors="black", linewidths=0.5)
    for _, r in merged.iterrows():
        ax.annotate(r["Driver"],
                    (r["TeamPerformanceScore"], r["PredictedLapTime"]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8)
    plt.colorbar(sc, ax=ax, label="Qualifying Time (s)")
    ax.set_xlabel("Team Performance Score")
    ax.set_ylabel("Predicted Avg Lap Time (s)")
    ax.set_title(f"Team Strength vs. Pace — {SEASON_YEAR} {gp_name}")
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name), "team_vs_pace.png"))
    plt.close(fig)


def plot_pace_vs_predicted(merged, gp_name="Grand Prix", save=True):
    fig, ax = plt.subplots(figsize=(12, 7))
    sc = ax.scatter(merged["CleanAirPace"], merged["PredictedLapTime"],
                    c=merged["TeamPerformanceScore"], cmap="coolwarm",
                    s=120, edgecolors="black", linewidths=0.5)
    for _, r in merged.iterrows():
        ax.annotate(r["Driver"],
                    (r["CleanAirPace"], r["PredictedLapTime"]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8)
    plt.colorbar(sc, ax=ax, label="Team Perf. Score")
    ax.set_xlabel("Clean Air Race Pace (s)")
    ax.set_ylabel("Predicted Avg Lap Time (s)")
    ax.set_title(f"Clean Air Pace vs. Predicted — {SEASON_YEAR} {gp_name}")
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name), "pace_vs_predicted.png"))
    plt.close(fig)


def _plot_team_driver_comparison(team_data, team, gp_name, save=True):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    colour = TEAM_COLOURS.get(team, "#888888")
    axes[0].bar(team_data["Driver"], team_data["PredictedLapTime"],
                color=colour, edgecolor="white")
    axes[0].set_ylabel("Predicted Avg Lap Time (s)"); axes[0].set_title("Predicted")
    for i, (_, r) in enumerate(team_data.iterrows()):
        axes[0].text(i, r["PredictedLapTime"]+0.01, f"{r['PredictedLapTime']:.2f}s",
                     ha="center", fontsize=9)
    axes[1].bar(team_data["Driver"], team_data["QualifyingTime"],
                color=colour, edgecolor="white")
    axes[1].set_ylabel("Qualifying Time (s)"); axes[1].set_title("Qualifying")
    for i, (_, r) in enumerate(team_data.iterrows()):
        axes[1].text(i, r["QualifyingTime"]+0.01, f"{r['QualifyingTime']:.2f}s",
                     ha="center", fontsize=9)
    x = np.arange(len(team_data)); w = 0.35
    axes[2].bar(x-w/2, team_data["PredictedLapTime_GB"], w, label="GB", color="#3671C6")
    axes[2].bar(x+w/2, team_data["PredictedLapTime_XGB"], w, label="XGB", color="#E8002D")
    axes[2].set_xticks(x); axes[2].set_xticklabels(team_data["Driver"])
    axes[2].set_ylabel("Pred. Time (s)"); axes[2].set_title("GB vs XGB"); axes[2].legend()
    fig.suptitle(f"{team} — {SEASON_YEAR} {gp_name}", fontsize=14, fontweight="bold")
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name, team), "driver_comparison.png"))
    plt.close(fig)


def _plot_team_summary_card(team_data, team, gp_name, all_merged, save=True):
    fig, ax = plt.subplots(figsize=(10, 6))
    colour = TEAM_COLOURS.get(team, "#888888")
    all_s = all_merged.sort_values("PredictedLapTime")
    bars = ax.barh(all_s["Driver"], all_s["PredictedLapTime"],
                   color="#DDDDDD", edgecolor="white")
    ax.invert_yaxis()
    team_drivers = set(team_data["Driver"])
    for bar, drv in zip(bars, all_s["Driver"]):
        if drv in team_drivers:
            bar.set_color(colour); bar.set_edgecolor("black"); bar.set_linewidth(1.5)
    ax.set_xlabel("Predicted Avg Lap Time (s)")
    ax.set_title(f"{team} highlighted — {SEASON_YEAR} {gp_name}")
    plt.tight_layout()
    if save: _save(fig, os.path.join(_viz_dir(gp_name, team), "grid_position.png"))
    plt.close(fig)


def generate_all_visualisations(results, merged, gp_name="Grand Prix", save=True):
    """Master function: generate all hierarchical visualisations."""
    root = _viz_dir(gp_name)
    teams = sorted(merged["Team"].unique())
    total = 4 + 2 * len(teams)
    pbar = tqdm(total=total, desc=f"Generating {gp_name} plots", unit="plot")

    plot_feature_importance(results, gp_name, save); pbar.update(1)
    plot_predicted_laptimes(merged, gp_name, save);  pbar.update(1)
    plot_team_vs_pace(merged, gp_name, save);        pbar.update(1)
    plot_pace_vs_predicted(merged, gp_name, save);   pbar.update(1)

    for team in teams:
        td = merged[merged["Team"] == team].copy()
        _plot_team_driver_comparison(td, team, gp_name, save); pbar.update(1)
        _plot_team_summary_card(td, team, gp_name, merged, save); pbar.update(1)

    pbar.close()
    print(f"\n✅ All visualisations saved under ./{root}/")
    return root


# ==========================================================================
# 10. HTML REPORT GENERATION
# ==========================================================================

def generate_html_report(classification, metrics, results, merged,
                         gp_name="Grand Prix", circuit_key="Australia",
                         gp_round=1, save=True):
    """Generate a self-contained HTML race report.

    Saved to  reports/<GP>/race_report.html
    """
    char = CIRCUIT_CHARACTERISTICS.get(circuit_key, {})
    cal  = CALENDAR.get(gp_round, {})
    viz  = _viz_dir(gp_name)

    # Build table rows
    rows_html = ""
    for pos, row in classification.iterrows():
        medal = {1:"🥇", 2:"🥈", 3:"🥉"}.get(pos, "")
        gap   = "—" if pos == 1 else f"+{row['Gap']:.3f}s"
        bg    = TEAM_COLOURS.get(row["Team"], "#888") + "20"
        rows_html += (
            f"<tr style='background:{bg}'>"
            f"<td>{medal} {pos}</td>"
            f"<td><b>{row['Driver']}</b></td>"
            f"<td>{row['DriverName']}</td>"
            f"<td>{row['Team']}</td>"
            f"<td>{row['PredictedLapTime']:.3f}s</td>"
            f"<td>{gap}</td>"
            f"<td><b>{row['Points']}</b></td></tr>\n"
        )

    # Metrics rows
    met_html = ""
    for _, r in metrics.iterrows():
        met_html += (f"<tr><td>{r['Model']}</td><td>{r['MAE (s)']:.4f}</td>"
                     f"<td>{r['RMSE (s)']:.4f}</td><td>{r['R²']:.4f}</td></tr>\n")

    # Constructor points
    cons = (classification.groupby("Team")["Points"].sum()
            .sort_values(ascending=False).reset_index())
    cons_html = ""
    for i, (_, r) in enumerate(cons.iterrows(), 1):
        cons_html += f"<tr><td>{i}</td><td>{r['Team']}</td><td>{r['Points']}</td></tr>\n"

    # Feature importance
    feat_cols = results["feature_cols"]
    gb_imp  = results["gb_model"].feature_importances_
    xgb_imp = results["xgb_model"].feature_importances_
    avg_imp = (gb_imp + xgb_imp) / 2
    fi_html = ""
    for idx in np.argsort(avg_imp)[::-1]:
        bar_w = int(avg_imp[idx] * 300)
        fi_html += (f"<tr><td>{feat_cols[idx]}</td>"
                    f"<td>{avg_imp[idx]:.4f}</td>"
                    f"<td><div style='background:#3671C6;width:{bar_w}px;"
                    f"height:16px;border-radius:3px'></div></td></tr>\n")

    # Spread stats
    pred = merged["PredictedLapTime"]
    spread = pred.max() - pred.min()

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{gp_name} — {SEASON_YEAR} Prediction Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 1100px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; }}
  h1 {{ color: #E8002D; border-bottom: 3px solid #E8002D; padding-bottom: 10px; }}
  h2 {{ color: #16213e; margin-top: 40px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #16213e; color: white; }}
  tr:hover {{ background: #f5f5f5; }}
  .podium {{ display: flex; gap: 20px; margin: 20px 0; }}
  .podium-card {{ flex: 1; padding: 20px; border-radius: 12px; text-align: center;
                  color: white; font-size: 1.1em; }}
  .p1 {{ background: linear-gradient(135deg, #FFD700, #FFA500); }}
  .p2 {{ background: linear-gradient(135deg, #C0C0C0, #A0A0A0); }}
  .p3 {{ background: linear-gradient(135deg, #CD7F32, #A0522D); }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 15px 0; }}
  .stat-card {{ background: #f0f4f8; padding: 15px; border-radius: 8px; text-align: center; }}
  .stat-card .value {{ font-size: 1.8em; font-weight: bold; color: #E8002D; }}
  .stat-card .label {{ color: #666; font-size: 0.9em; }}
  .meta {{ color: #666; font-size: 0.95em; }}
  .img-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }}
  .img-grid img {{ width: 100%; border-radius: 8px; border: 1px solid #ddd; }}
</style></head><body>
<h1>🏁 {gp_name} — {SEASON_YEAR} Prediction Report</h1>
<p class="meta">Circuit: {cal.get('circuit', char.get('type',''))} |
   Laps: {cal.get('laps', '—')} | Date: {cal.get('date', '—')} |
   Expected pit stops: {char.get('expected_stops','—')} |
   Tyre degradation: {char.get('tyre_deg','—')}</p>

<h2>🏆 Podium</h2>
<div class="podium">
  <div class="podium-card p1">🥇 WINNER<br><b>{classification.iloc[0]['DriverName']}</b><br>{classification.iloc[0]['Team']}<br>{classification.iloc[0]['Points']} pts</div>
  <div class="podium-card p2">🥈 2nd<br><b>{classification.iloc[1]['DriverName']}</b><br>{classification.iloc[1]['Team']}<br>{classification.iloc[1]['Points']} pts</div>
  <div class="podium-card p3">🥉 3rd<br><b>{classification.iloc[2]['DriverName']}</b><br>{classification.iloc[2]['Team']}<br>{classification.iloc[2]['Points']} pts</div>
</div>

<h2>📊 Full Classification</h2>
<table><tr><th>Pos</th><th>Code</th><th>Driver</th><th>Team</th><th>Pred. Time</th><th>Gap</th><th>Pts</th></tr>
{rows_html}</table>

<h2>🏗️ Constructor Points</h2>
<table><tr><th>Pos</th><th>Team</th><th>Points</th></tr>
{cons_html}</table>

<h2>🤖 Model Evaluation</h2>
<table><tr><th>Model</th><th>MAE (s)</th><th>RMSE (s)</th><th>R²</th></tr>
{met_html}</table>

<div class="stat-grid">
  <div class="stat-card"><div class="value">{len(results['X_imputed'])}</div><div class="label">Training Samples</div></div>
  <div class="stat-card"><div class="value">{len(results['feature_cols'])}</div><div class="label">Features</div></div>
  <div class="stat-card"><div class="value">{spread:.2f}s</div><div class="label">Pred. Spread</div></div>
</div>

<h2>📈 Feature Importance (Ensemble Avg)</h2>
<table><tr><th>Feature</th><th>Importance</th><th>Bar</th></tr>
{fi_html}</table>

<h2>📷 Visualisations</h2>
<div class="img-grid">
  <img src="../../{viz}/predicted_laptimes.png" alt="Lap Times">
  <img src="../../{viz}/feature_importance.png" alt="Feature Importance">
  <img src="../../{viz}/team_vs_pace.png" alt="Team vs Pace">
  <img src="../../{viz}/pace_vs_predicted.png" alt="Pace vs Predicted">
</div>

<p class="meta" style="margin-top:40px;text-align:center">
  Generated by F1 Prediction Framework v2.0 — {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""

    if save:
        report_dir = os.path.join("reports", _safe_name(gp_name))
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, "race_report.html")
        with open(path, "w") as f:
            f.write(html)
        print(f"📄 Report saved to {path}")
        return path
    return html
