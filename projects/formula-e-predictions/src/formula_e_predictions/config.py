"""Formula E configuration: calendar, roster, teams, points, and model knobs.

Formula E is the fourth series on the MotorsportVerse core, cloned from the F3
golden template and adapted to FE's sporting structure. This module is the only
FE-domain knowledge the project carries; everything numerically heavy is reused
from motorsport-core / motorsport-data.

Season keying
-------------
FE seasons span the new year ("SEASON 2025-2026"), so the project keys every
season by its **ending year**: ``SEASON = 2026`` means the 2025-26 championship.
:data:`SEASON_LABEL` carries the human/API label.

Results data
------------
Results come from the official Pulselive API
(``api.formula-e.pulselive.com/formula-e/v1`` — no auth; see
``sources/pulselive_source.py``). The committed snapshot
(``data/official_2026.json``) carries the real season and every downstream
build reads it offline; the deterministic latent-pace generator
(:data:`_TRUTH_PACE`) remains the always-available fallback that keeps the
pipeline functional and testable end-to-end. The predictor never sees
``_TRUTH_PACE`` — it estimates pace from prior results only (leakage-safe).

The 2025-26 sporting facts below (17 points races incl. four doubleheaders,
20-car grid, points 25-18-15-12-10-8-6-4-2-1 plus pole +3 and fastest-lap +1)
were verified against the live Pulselive API on 2026-07-07/08, not assumed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from motorsport_data.schema import Team, Venue

SPORT = "Formula E"

# --------------------------------------------------------------------------- #
# Season selection (multi-season rollover support — see season_rollover.py).
#
# The literal tables below describe the 2025-26 season (key 2026). A future
# season becomes active when ``season_rollover.py --start`` drops a marker file
# (``data/active_season.json``) after ``bootstrap_next_season.py`` has written
# an announced-calendar file (``data/announced_seasons/<year>.json``). With no
# marker and no ``FE_SEASON_YEAR`` env override, this module behaves exactly as
# it always has (the 2026 literals).
# --------------------------------------------------------------------------- #
_DEFAULT_SEASON = 2026
# ``FE_DATA_DIR`` is a test seam only; unset in production.
_DATA_DIR = Path(os.environ.get("FE_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("FE_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


def season_label(year: int) -> str:
    """The Pulselive championship label for a season keyed by ending year."""
    return f"SEASON {year - 1}-{year}"


SEASON_LABEL = season_label(SEASON)


def _load_announced_season(year: int) -> dict | None:
    """The announced-calendar payload for ``year`` (None when absent/invalid)."""
    path = _DATA_DIR / "announced_seasons" / f"{year}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(payload.get("season", 0)) != year or not payload.get("calendar"):
        return None
    return payload


_ANNOUNCED: dict | None = None if SEASON == _DEFAULT_SEASON else _load_announced_season(SEASON)
if SEASON != _DEFAULT_SEASON and _ANNOUNCED is None:
    raise RuntimeError(
        f"FE season {SEASON} is active but data/announced_seasons/{SEASON}.json is missing or "
        "invalid — run `python -m formula_e_predictions.bootstrap_next_season` first."
    )

# --------------------------------------------------------------------------- #
# Calendar — the 17 points races of the 2025-26 championship, verified against
# the Pulselive race list (seriesType FE_REGULAR; test events are a separate
# FE_TESTS championship and never appear here). **Every race is one round** —
# a doubleheader is two consecutive rounds sharing a venue key/city, exactly
# how the official race numbering works. Venue ``kind`` distinguishes street
# circuits (most of the calendar) from permanent road courses — it is the
# calibration stratum (street racing is higher-variance; the calibrator finds
# out by how much rather than the model clamping it).
# --------------------------------------------------------------------------- #
CALENDAR: list[Venue] = [
    Venue(key="sao-paulo", name="São Paulo", country="Brazil", kind="street"),
    Venue(key="mexico-city", name="Mexico City", country="Mexico", kind="circuit"),
    Venue(key="miami", name="Miami", country="United States", kind="circuit"),
    Venue(key="jeddah", name="Jeddah", country="Saudi Arabia", kind="street"),
    Venue(key="jeddah", name="Jeddah II", country="Saudi Arabia", kind="street"),
    Venue(key="madrid", name="Madrid", country="Spain", kind="circuit"),
    Venue(key="berlin", name="Berlin", country="Germany", kind="street"),
    Venue(key="berlin", name="Berlin II", country="Germany", kind="street"),
    Venue(key="monaco", name="Monaco", country="Monaco", kind="street"),
    Venue(key="monaco", name="Monaco II", country="Monaco", kind="street"),
    Venue(key="sanya", name="Sanya", country="China", kind="street"),
    Venue(key="shanghai", name="Shanghai", country="China", kind="circuit"),
    Venue(key="shanghai", name="Shanghai II", country="China", kind="circuit"),
    Venue(key="tokyo", name="Tokyo", country="Japan", kind="street"),
    Venue(key="tokyo", name="Tokyo II", country="Japan", kind="street"),
    Venue(key="london", name="London", country="United Kingdom", kind="street"),
    Venue(key="london", name="London II", country="United Kingdom", kind="street"),
]

# Per-round metadata: city + the race date (FE runs ONE race per round; a
# doubleheader is simply two rounds on consecutive days). A round is
# "completed" once its results are published — the data layer derives
# completion from the feed, never the wall clock (see export.py).
CALENDAR_META: dict[int, dict[str, str]] = {
    1: {"city": "São Paulo", "date": "2025-12-06"},
    2: {"city": "Mexico City", "date": "2026-01-10"},
    3: {"city": "Miami", "date": "2026-01-31"},
    4: {"city": "Jeddah", "date": "2026-02-13"},
    5: {"city": "Jeddah", "date": "2026-02-14"},
    6: {"city": "Madrid", "date": "2026-03-21"},
    7: {"city": "Berlin", "date": "2026-05-02"},
    8: {"city": "Berlin", "date": "2026-05-03"},
    9: {"city": "Monaco", "date": "2026-05-16"},
    10: {"city": "Monaco", "date": "2026-05-17"},
    11: {"city": "Sanya", "date": "2026-06-20"},
    12: {"city": "Shanghai", "date": "2026-07-04"},
    13: {"city": "Shanghai", "date": "2026-07-05"},
    14: {"city": "Tokyo", "date": "2026-07-25"},
    15: {"city": "Tokyo", "date": "2026-07-26"},
    16: {"city": "London", "date": "2026-08-15"},
    17: {"city": "London", "date": "2026-08-16"},
}

# Announced (post-2026) seasons override the literal calendar from the payload
# written by bootstrap_next_season.py / a human-installed announced calendar.
if _ANNOUNCED:
    CALENDAR = [
        Venue(key=e["key"], name=e["name"], country=e["country"], kind=e.get("kind", "street"))
        for e in _ANNOUNCED["calendar"]
    ]
    CALENDAR_META = {
        int(e.get("round", i)): {
            "city": e.get("city", ""),
            "date": e.get("date", ""),
        }
        for i, e in enumerate(_ANNOUNCED["calendar"], start=1)
    }


# How many rounds are "in the books". Derived from the committed real-data
# snapshot (data/official_2026.json) so one `python -m formula_e_predictions.refresh`
# advances the whole pipeline; falls back to a literal if the snapshot is absent.
def _completed_from_snapshot(default: int = 13) -> int:
    snap_path = _DATA_DIR / f"official_{SEASON}.json"
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        if snap.get("season") == SEASON and "completedRounds" in snap:
            return int(snap["completedRounds"])
    except Exception:
        pass
    return default


# A freshly started (announced) season has no snapshot yet — 0 rounds complete.
COMPLETED_ROUNDS = _completed_from_snapshot(default=13 if SEASON == _DEFAULT_SEASON else 0)

# --------------------------------------------------------------------------- #
# Teams — the ten 2025-26 entrants. Display names are curated; the API serves
# ALL-CAPS entrant names, normalised through TEAM_ALIASES at ingestion.
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="Andretti", color="#F26522"),
    Team(name="Citroën Racing", color="#EB002A"),
    Team(name="CUPRA KIRO", color="#2AA8A0"),
    Team(name="DS Penske", color="#CBA65F"),
    Team(name="Envision Racing", color="#00C900"),
    Team(name="Jaguar TCS Racing", color="#C9A227"),
    Team(name="Lola Yamaha ABT", color="#0033A0"),
    Team(name="Mahindra Racing", color="#E31837"),
    Team(name="Nissan", color="#E4287C"),
    Team(name="Porsche", color="#D5001C"),
]

# Pulselive entrant names → curated display names (applied at ingestion so the
# snapshot, standings, and model all speak one vocabulary).
TEAM_ALIASES: dict[str, str] = {
    "ANDRETTI FORMULA E": "Andretti",
    "CITROËN RACING": "Citroën Racing",
    "CUPRA KIRO": "CUPRA KIRO",
    "DS PENSKE": "DS Penske",
    "ENVISION RACING": "Envision Racing",
    "JAGUAR TCS RACING": "Jaguar TCS Racing",
    "LOLA YAMAHA ABT FORMULA E TEAM": "Lola Yamaha ABT",
    "MAHINDRA RACING": "Mahindra Racing",
    "NISSAN FORMULA E TEAM": "Nissan",
    "PORSCHE FORMULA E TEAM": "Porsche",
}

if _ANNOUNCED and _ANNOUNCED.get("teams"):
    TEAMS = [Team(name=t["name"], color=t.get("color", "#888888")) for t in _ANNOUNCED["teams"]]

# --------------------------------------------------------------------------- #
# Driver roster — code (Pulselive TLA), name, team. Two per team (20-car grid),
# as raced at the most recent completed round. The 2025-26 grid has had no
# mid-season seat changes through round 13 (verified against every round's
# classification).
# --------------------------------------------------------------------------- #
# (code, name, team, latent_pace)  — lower latent_pace = faster (seconds proxy).
# Pace is used ONLY by the synthetic fallback generator, never the predictor.
_ROSTER: list[tuple[str, str, str, float]] = [
    ("WEH", "P. Wehrlein", "Porsche", 88.90),
    ("EVA", "M. Evans", "Jaguar TCS Racing", 88.98),
    ("ROW", "O. Rowland", "Nissan", 89.05),
    ("DAC", "A. Félix da Costa", "Jaguar TCS Racing", 89.10),
    ("DEN", "J. Dennis", "Andretti", 89.15),
    ("MOR", "E. Mortara", "Mahindra Racing", 89.22),
    ("MUE", "N. Müller", "Porsche", 89.28),
    ("BUE", "S. Buemi", "Envision Racing", 89.45),
    ("CAS", "N. Cassidy", "Citroën Racing", 89.50),
    ("DEV", "N. de Vries", "Mahindra Racing", 89.55),
    ("DRU", "F. Drugovich", "Andretti", 89.60),
    ("MAR", "J. M. Martí", "CUPRA KIRO", 89.70),
    ("ERI", "J. Eriksson", "Envision Racing", 89.75),
    ("JEV", "J-É. Vergne", "Citroën Racing", 89.85),
    ("DIG", "L. Di Grassi", "Lola Yamaha ABT", 89.95),
    ("TIC", "D. Ticktum", "CUPRA KIRO", 90.05),
    ("BAR", "T. Barnard", "DS Penske", 90.08),
    ("GUE", "M. Günther", "DS Penske", 90.15),
    ("NAT", "N. Nato", "Nissan", 90.30),
    ("MAL", "Z. Maloney", "Lola Yamaha ABT", 90.45),
]

# An announced season carries its own (provisional) roster forward.
if _ANNOUNCED and _ANNOUNCED.get("roster"):
    _ROSTER = [
        (r["code"], r["name"], r["team"], float(r.get("pace", 90.0)))
        for r in _ANNOUNCED["roster"]
    ]

DRIVERS: list[dict[str, str]] = [
    {"code": c, "name": n, "team": t} for (c, n, t, _) in _ROSTER
]

# Drivers replaced mid-season: not on the current roster but present in earlier
# classifications and the official standings, so the team-points aggregation
# still needs their team mapping. Empty for 2025-26 (no seat changes yet) —
# refresh.py warns if a scraped classification carries an unknown code.
FORMER_DRIVERS: dict[str, dict[str, str]] = {}

if _ANNOUNCED:
    FORMER_DRIVERS = {
        code: {"name": d.get("name", code), "team": d.get("team", "")}
        for code, d in (_ANNOUNCED.get("former_drivers") or {}).items()
    }

TEAM_OF: dict[str, str] = {c: t for (c, _, t, _) in _ROSTER} | {
    c: d["team"] for c, d in FORMER_DRIVERS.items()
}
DRIVER_NAME: dict[str, str] = {c: n for (c, n, _, _) in _ROSTER} | {
    c: d["name"] for c, d in FORMER_DRIVERS.items()
}

# Latent pace — used ONLY by the synthetic results generator, never the predictor.
_TRUTH_PACE: dict[str, float] = {c: p for (c, _, _, p) in _ROSTER}

# --------------------------------------------------------------------------- #
# Points — 2025-26 FE, verified against live classifications (round 13:
# Drugovich P6 scored 8+3 with pole; Rowland P8 scored 4+1 with fastest lap).
# The pole and fastest-lap bonuses ride on flags in the API result rows.
# --------------------------------------------------------------------------- #
POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
POLE_POINTS = 3          # awarded to the duels-final winner (grid P1)
FASTEST_LAP_POINTS = 1   # if classified in the top 10

# --------------------------------------------------------------------------- #
# Regulation eras — FE's Gen table (the FE analog of motorsport_core.era.ERAS,
# which ships F1's table; core does not yet accept a custom table, so the
# boundary seasons live here and model.py applies the same hard-cut semantics).
# Seasons are keyed by ENDING year.
# --------------------------------------------------------------------------- #
FE_ERAS: tuple[tuple[str, int, int | None], ...] = (
    ("gen1", 2015, 2018),       # Gen1: car swaps mid-race
    ("gen2", 2019, 2022),       # Gen2: full race distance, attack mode
    ("gen3", 2023, 2024),       # Gen3: 350 kW, no rear brakes
    ("gen3_evo", 2025, None),   # Gen3 Evo: AWD attack mode, faster 0-100
)

# ML training window: the Gen3 era onward (2022-23 season = key 2023). Earlier
# seasons only feed the Elo / era priors, never the learned regressors.
ML_FIRST_SEASON = 2023
# Elo seed window: prior seasons replayed into the rating stack before the
# active season's rounds (Gen2 onward; Gen1 is two era boundaries away and is
# hard-cut, mirroring motorsport_core.era.DEFAULT_MAX_ERA_DISTANCE = 1).
ELO_FIRST_SEASON = 2019

# --------------------------------------------------------------------------- #
# FE model parameters — the tuning knobs of the FE model (see model.py).
#
# FE runs a spec chassis/battery with manufacturer powertrains: the driver
# effect dominates and the team effect is real but modest — weighted well below
# the driver signals (the F3 spec-series convention, softened slightly for the
# powertrain differences).
# --------------------------------------------------------------------------- #

# Pace scale (a seconds-like proxy the Plackett-Luce sampler reads; lower = faster).
PACE_BASE = 90.0           # neutral pace when there is no signal yet
PACE_SPREAD = 0.50         # seconds per unit of blended-skill z-score

# Blend weights for the latent skill (relative; need not sum to 1). Driver-level
# signals (elo, finishing history) dominate; ``team`` is small but non-zero
# (manufacturer powertrains matter more than in a pure one-make series).
# ``ml`` weights the optional gradient-boosted regressor (see ``ml_skill.py``);
# ``bayes`` the optional PyMC posterior. Both fold in only when available.
SKILL_WEIGHTS = {"elo": 0.55, "history": 0.45, "team": 0.18, "ml": 0.5, "bayes": 0.5}

# Post-quali: when the REAL qualifying order is known, the forecast conditions
# on the actual grid. Track position matters on FE's tight street circuits —
# more than an F3 feature race, less than the reverse-grid sprint — so a
# moderate per-slot pace cost nudges the forecast toward the real grid without
# overpowering skill. Unused pre-quali (pure-pace merit grid).
GRID_WEIGHT = 0.08  # seconds of pace cost per grid slot back

# A driver with fewer than this many prior race entries (across the Elo window)
# is treated as a rookie (pooled toward the team mean by the Elo prior; used as
# a calibration stratum). FE grids are veteran-heavy — rookies are rare.
ROOKIE_RACE_THRESHOLD = 3

# Monte Carlo sample count for the per-round probability + championship layers.
DEFAULT_SAMPLES = 4000

# Opt-in Bayesian hierarchical skill prior (motorsport_core.hierarchical_bayes).
# Off by default: PyMC is an optional, slow dependency and CI must stay
# deterministic. Degrades silently to Elo + history when unavailable.
USE_BAYESIAN_SKILL = False

# Opt-in gradient-boosted skill regressor (formula_e_predictions.ml_skill) —
# the F1-parity ensemble signal. ON by default but conservatively weighted;
# degrades silently to the Elo+history blend when deps/data are missing.
USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 2     # need >= 2 prior rounds so features have variance / a trend
ML_MIN_TRAIN_ROWS = 8       # minimum raced-driver rows before a fit is trustworthy
ML_MIN_SPLIT_ROWS = 12      # below this, score weights in-sample instead of splitting

# --------------------------------------------------------------------------- #
# Real data feed + calibration.
#
# Results are selected at runtime (see datasource.py): the committed snapshot
# (real, offline) with the synthetic generator behind it by default, or a
# live-first composite when ``FE_USE_LIVE_RESULTS=1``. Probability calibration
# only turns on once enough *real* rounds have been observed — the honest gate
# that keeps the website from claiming calibration it hasn't earned.
# --------------------------------------------------------------------------- #
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4

# --------------------------------------------------------------------------- #
# Pulselive API (see sources/pulselive_source.py). No auth; be a polite guest:
# honest UA, ~1 request/second, disk-cached raw responses during backfill.
# --------------------------------------------------------------------------- #
PULSELIVE_BASE_URL = "https://api.formula-e.pulselive.com/formula-e/v1"
PULSELIVE_USER_AGENT = "motorsportverse/1.0"

# season (ending year) -> Pulselive championship id. The 2026 id is pinned as a
# verified anchor + wrong-season guard; other seasons are discovered from the
# race list (championship name "SEASON <y-1>-<y>", seriesType FE_REGULAR).
CHAMPIONSHIP_IDS: dict[int, str] = {
    2026: "8088703b-96c1-410d-a48b-77fca322334f",
}
