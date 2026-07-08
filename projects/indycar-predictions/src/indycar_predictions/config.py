"""NTT IndyCar Series sporting constants.

IndyCar has NO public results API, so this project inverts the usual source
hierarchy: **committed, human-verified data files are the source of truth**
(``data/history_<year>.json``, curated from Wikipedia and verified against the
official standings — see ``data/CURATION_REPORT.md``), and live scraping is
only a refresh mechanism behind strict validation (:mod:`.refresh`).

Points provenance (verified against the curated data, 2026-07-08)
-----------------------------------------------------------------
The curated files record points **as officially awarded** (parsed from each
race's classification table, bonuses included). The base race-points table
below was cross-checked against the modal awarded value per finishing position
across the 2016-2026 full-detail rounds: winner 50, then 40, 35, 32, 30, 28,
26, 24, 22, 20, then -1 per position down to 5 at 25th; 26th and beyond score
5. The modal *awarded* winner value is 51-53 because bonuses ride on top:
+1 pole, +1 for leading a lap, +2 for most laps led (and Indy-500 qualifying
points at the 500). Standings are always computed from the awarded points in
the data, never re-derived from this table — the table exists for the
grid-backed old rounds that lack per-race points and for the championship
Monte Carlo of future rounds.

Indy 500 double points: the 2026 curated data shows the 500's winner earned
**60 points** (50 base + qualifying/lap bonuses), NOT ~100 — so the 500 does
NOT pay double points in 2026 (double points last appeared in the 2014-2015
curated seasons: e.g. 2014 round 5 winner 126). Encoded below as
``INDY500_DOUBLE_POINTS = False``; the championship projection therefore needs
no extra-race fold.
"""
from __future__ import annotations

import json as _json
import os as _os
import re as _re
import unicodedata as _unicodedata
from pathlib import Path as _Path

from motorsport_data.schema import Team, Venue

SPORT = "IndyCar"

# --------------------------------------------------------------------------- #
# Season selection (multi-season rollover support — see season_rollover.py).
# ``INDYCAR_DATA_DIR`` is a test seam only; unset in production.
# --------------------------------------------------------------------------- #
_DEFAULT_SEASON = 2026
_DATA_DIR = _Path(
    _os.environ.get("INDYCAR_DATA_DIR") or _Path(__file__).resolve().parents[2] / "data"
)


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = _os.environ.get("INDYCAR_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = _json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


def season_label(year: int) -> str:
    """IndyCar seasons are calendar-year seasons."""
    return str(year)


SEASON_LABEL = season_label(SEASON)


def _load_announced_season(year: int) -> dict | None:
    """The announced-calendar payload for ``year`` (None when absent/invalid)."""
    path = _DATA_DIR / "announced_seasons" / f"{year}.json"
    try:
        payload = _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(payload.get("season", 0)) != year or not payload.get("calendar"):
        return None
    return payload


_ANNOUNCED: dict | None = None if SEASON == _DEFAULT_SEASON else _load_announced_season(SEASON)
if SEASON != _DEFAULT_SEASON and _ANNOUNCED is None:
    raise RuntimeError(
        f"IndyCar season {SEASON} is active but data/announced_seasons/{SEASON}.json is "
        "missing or invalid — run `python -m indycar_predictions.bootstrap_next_season` first."
    )

# --------------------------------------------------------------------------- #
# Race points (1-based finishing position -> BASE points, bonuses excluded).
# Unchanged since 2012 per the curated seasons (see module docstring).
# --------------------------------------------------------------------------- #
POINTS: dict[int, int] = {
    1: 50, 2: 40, 3: 35, 4: 32, 5: 30, 6: 28, 7: 26, 8: 24, 9: 22, 10: 20,
    **{p: 30 - p for p in range(11, 25)},   # 11th = 19 ... 24th = 6
    **{p: 5 for p in range(25, 36)},        # 25th and beyond score 5
}

#: Bonus points that ride on top of the base table (recorded as awarded in the
#: curated data; used only to fold an *expectation* into the championship MC).
POLE_BONUS = 1
LED_LAP_BONUS = 1
MOST_LAPS_LED_BONUS = 2

#: 2026 curated data: the 500's winner scored 60, not ~100 — no double points.
INDY500_DOUBLE_POINTS = False

# --------------------------------------------------------------------------- #
# Track types — THE model stratum for IndyCar. An oval and a road/street
# course are nearly different sports (different specialists, different
# attrition), so the model keeps a DUAL Elo: one oval instance, one pooled
# road/street instance (street and permanent road courses share the
# braking/kerbs skill set far more than either shares with pack-oval racing).
# Calibration is stratified by the full three-way track type.
# --------------------------------------------------------------------------- #
TRACK_TYPES: tuple[str, ...] = ("oval", "road", "street")
ELO_TRACK_GROUPS: tuple[str, ...] = ("oval", "road_street")


def track_group_of(track_type: str) -> str:
    """The dual-Elo group of a track type: oval vs road/street."""
    return "oval" if track_type == "oval" else "road_street"


def driver_code(name: str) -> str:
    """Deterministic, season-stable driver code from a full name.

    First two letters of the first name + the full surname (suffixes dropped),
    ASCII-folded and uppercased: "Álex Palou" → ALPALOU, "Marcus Ericsson" →
    MAERICSSON vs "Marcus Armstrong" → MAARMSTRONG. Stable across seasons and
    accent-insensitive (the curated data spells "Sébastien Bourdais" both with
    and without accents; both fold to SEBOURDAIS).
    """
    s = _unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = _re.sub(r"[^A-Za-z ]", " ", s)
    toks = [t for t in s.split() if t.upper() not in {"JR", "SR", "II", "III", "IV", "V"}]
    if not toks:
        return "UNKNOWN"
    if len(toks) == 1:
        return toks[0].upper()
    return (toks[0][:2] + toks[-1]).upper()


# --------------------------------------------------------------------------- #
# Calendar — loaded from the committed, human-verified calendar file
# (data/calendar_2026.json, curated alongside the history files). 18 rounds;
# round 7 is the Indianapolis 500 (33-car field, May qualifying window).
# --------------------------------------------------------------------------- #
def _load_calendar_file(year: int) -> list[dict]:
    path = _DATA_DIR / f"calendar_{year}.json"
    payload = _json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("season", 0)) != year:
        raise RuntimeError(f"calendar file {path} is not for season {year}")
    return list(payload["calendar"])


def _cal(rnd: int, entry: dict) -> dict:
    venue = entry.get("venue", f"Round {rnd}")
    track_type = entry.get("track_type", entry.get("trackType", "road"))
    return {
        "round": rnd,
        "key": entry.get("venue_key") or entry.get("key") or f"round-{rnd}",
        "venue": venue,
        "raceName": entry.get("name", entry.get("raceName", venue)),
        "date": entry.get("date", ""),
        "trackType": track_type,
        "kind": "oval" if track_type == "oval" else ("street" if track_type == "street" else "circuit"),
    }


if _ANNOUNCED:
    _CAL_ACTIVE: list[dict] = [
        _cal(int(e.get("round", i)), e) for i, e in enumerate(_ANNOUNCED["calendar"], start=1)
    ]
else:
    _CAL_ACTIVE = [_cal(int(e["round"]), e) for e in _load_calendar_file(SEASON)]

CALENDAR: list[Venue] = [
    Venue(key=e["key"], name=e["venue"], country="United States", kind=e["kind"])
    for e in _CAL_ACTIVE
]

#: round -> the full calendar metadata dict (venue, raceName, date, trackType,
#: kind). The freshness gate, the wrong-event guard and the export all read
#: this one table.
CALENDAR_META: dict[int, dict] = {e["round"]: e for e in _CAL_ACTIVE}


def is_indy500_round(rnd: int) -> bool:
    """Is this round the Indianapolis 500 (oval at IMS, 33-car field)?"""
    meta = CALENDAR_META.get(rnd, {})
    return meta.get("trackType") == "oval" and "indianapolis-motor-speedway" == meta.get("key")


#: Rounds that are the Indy 500 in the active calendar (normally exactly one).
INDY500_ROUNDS: tuple[int, ...] = tuple(r for r in CALENDAR_META if is_indy500_round(r))


# How many rounds are "in the books". Derived from the committed snapshot
# (data/history_<SEASON>.json — the single active-season source of truth) so
# one `python -m indycar_predictions.refresh` advances the whole pipeline.
def _completed_from_snapshot(default: int) -> int:
    try:
        snap = _json.loads((_DATA_DIR / f"history_{SEASON}.json").read_text(encoding="utf-8"))
        if int(snap.get("season", 0)) == SEASON and snap.get("rounds"):
            return len(snap["rounds"])
    except Exception:
        pass
    return default


COMPLETED_ROUNDS = _completed_from_snapshot(default=11 if SEASON == _DEFAULT_SEASON else 0)

# --------------------------------------------------------------------------- #
# Teams & engine manufacturers. IndyCar has two team-like groupings: the
# racing team (Ganassi, Penske, McLaren — the Elo/rookie-pooling unit) and the
# engine manufacturer (Chevrolet / Honda — a broader shared effect the model
# carries separately, the analog of NASCAR's make).
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="Chip Ganassi Racing", color="#D31217"),
    Team(name="Team Penske", color="#FFD100"),
    Team(name="Arrow McLaren", color="#FF8000"),
    Team(name="Andretti Global", color="#0A66C2"),
    Team(name="Meyer Shank Racing", color="#E5398D"),
    Team(name="Rahal Letterman Lanigan Racing", color="#1D449B"),
    Team(name="ECR", color="#8626EC"),
    Team(name="A.J. Foyt Enterprises", color="#B22222"),
    Team(name="Dale Coyne Racing", color="#5A5A5A"),
    Team(name="Juncos Hollinger Racing", color="#00A19C"),
    Team(name="Dreyer & Reinbold Racing", color="#777777"),
    Team(name="Abel Motorsports", color="#2E8B57"),
    Team(name="HMD Motorsports", color="#101820"),
]

ENGINES: tuple[str, ...] = ("Chevrolet", "Honda")
ENGINE_COLORS: dict[str, str] = {"Chevrolet": "#C6A96E", "Honda": "#CC0000"}

# --------------------------------------------------------------------------- #
# Driver roster — the 25 full-season entries of 2026 (every one started all 11
# completed rounds), in current championship order, plus the Indy-500-only
# entries (round 7 ran the traditional 33-car field). Derived from the
# committed curated data (data/history_2026.json) on 2026-07-08.
# (code, name, team, engine, latent_pace) — lower latent_pace = faster; pace
# is used ONLY by the synthetic fallback generator, never the predictor.
# --------------------------------------------------------------------------- #
_ROSTER: list[tuple[str, str, str, str, float]] = [
    ("ALPALOU", "Álex Palou", "Chip Ganassi Racing", "Honda", 89.80),
    ("KYKIRKWOOD", "Kyle Kirkwood", "Andretti Global", "Honda", 89.85),
    ("CHLUNDGAARD", "Christian Lundgaard", "Arrow McLaren", "Chevrolet", 89.90),
    ("DAMALUKAS", "David Malukas", "Team Penske", "Chevrolet", 89.95),
    ("PAWARD", "Pato O'Ward", "Arrow McLaren", "Chevrolet", 90.00),
    ("JONEWGARDEN", "Josef Newgarden", "Team Penske", "Chevrolet", 90.05),
    ("FEROSENQVIST", "Felix Rosenqvist", "Meyer Shank Racing", "Honda", 90.10),
    ("SCMCLAUGHLIN", "Scott McLaughlin", "Team Penske", "Chevrolet", 90.15),
    ("SCDIXON", "Scott Dixon", "Chip Ganassi Racing", "Honda", 90.20),
    ("MAERICSSON", "Marcus Ericsson", "Andretti Global", "Honda", 90.25),
    ("RIVEEKAY", "Rinus VeeKay", "Juncos Hollinger Racing", "Chevrolet", 90.30),
    ("MAARMSTRONG", "Marcus Armstrong", "Meyer Shank Racing", "Honda", 90.35),
    ("GRRAHAL", "Graham Rahal", "Rahal Letterman Lanigan Racing", "Honda", 90.40),
    ("WIPOWER", "Will Power", "Andretti Global", "Honda", 90.45),
    ("KYSIMPSON", "Kyffin Simpson", "Chip Ganassi Racing", "Honda", 90.50),
    ("ALROSSI", "Alexander Rossi", "ECR", "Chevrolet", 90.55),
    ("SAFERRUCCI", "Santino Ferrucci", "A.J. Foyt Enterprises", "Chevrolet", 90.60),
    ("LOFOSTER", "Louis Foster", "Rahal Letterman Lanigan Racing", "Honda", 90.65),
    ("DEHAUGER", "Dennis Hauger", "Dale Coyne Racing", "Honda", 90.70),
    ("NOSIEGEL", "Nolan Siegel", "Arrow McLaren", "Chevrolet", 90.75),
    ("CHRASMUSSEN", "Christian Rasmussen", "ECR", "Chevrolet", 90.80),
    ("ROGROSJEAN", "Romain Grosjean", "Dale Coyne Racing", "Honda", 90.85),
    ("CACOLLET", "Caio Collet", "A.J. Foyt Enterprises", "Chevrolet", 90.90),
    ("STROBB", "Sting Ray Robb", "Juncos Hollinger Racing", "Chevrolet", 90.95),
    ("MISCHUMACHER", "Mick Schumacher", "Rahal Letterman Lanigan Racing", "Honda", 91.00),
]

# An announced season carries its own (provisional) roster forward.
if _ANNOUNCED and _ANNOUNCED.get("roster"):
    _ROSTER = [
        (r["code"], r["name"], r["team"], r.get("engine", ""), float(r.get("pace", 90.5)))
        for r in _ANNOUNCED["roster"]
    ]

DRIVERS: list[dict[str, str]] = [
    {"code": c, "name": n, "team": t, "engine": e} for (c, n, t, e, _) in _ROSTER
]

# Entrants seen in 2026 but not on the full-season roster — the Indy-500-only
# / one-off entries, so team/engine lookups and standings aggregation never
# miss a code. refresh.py refuses a scraped classification dominated by codes
# neither table knows (the roster-whitelist guard).
INDY500_ONLY_DRIVERS: dict[str, dict[str, str]] = {
    "CODALY": {"name": "Conor Daly", "team": "Dreyer & Reinbold Racing", "engine": "Chevrolet"},
    "TASATO": {"name": "Takuma Sato", "team": "Rahal Letterman Lanigan Racing", "engine": "Honda"},
    "JAHARVEY": {"name": "Jack Harvey", "team": "Dreyer & Reinbold Racing", "engine": "Chevrolet"},
    "JAABEL": {"name": "Jacob Abel", "team": "Abel Motorsports", "engine": "Chevrolet"},
    "HECASTRONEVES": {"name": "Hélio Castroneves", "team": "Meyer Shank Racing", "engine": "Honda"},
    "EDCARPENTER": {"name": "Ed Carpenter", "team": "ECR", "engine": "Chevrolet"},
    "RYREAY": {"name": "Ryan Hunter-Reay", "team": "Arrow McLaren", "engine": "Chevrolet"},
    "KALEGGE": {"name": "Katherine Legge", "team": "HMD Motorsports", "engine": "Chevrolet"},
}
#: Family-parity alias (the NASCAR project calls this PART_TIME_DRIVERS).
PART_TIME_DRIVERS = INDY500_ONLY_DRIVERS

if _ANNOUNCED:
    PART_TIME_DRIVERS = INDY500_ONLY_DRIVERS = {
        code: {
            "name": d.get("name", code),
            "team": d.get("team", ""),
            "engine": d.get("engine", ""),
        }
        for code, d in (_ANNOUNCED.get("part_time_drivers") or {}).items()
    }

TEAM_OF: dict[str, str] = {c: t for (c, _, t, _, _) in _ROSTER} | {
    c: d["team"] for c, d in INDY500_ONLY_DRIVERS.items()
}
DRIVER_NAME: dict[str, str] = {c: n for (c, n, _, _, _) in _ROSTER} | {
    c: d["name"] for c, d in INDY500_ONLY_DRIVERS.items()
}
ENGINE_OF: dict[str, str] = {c: e for (c, _, _, e, _) in _ROSTER} | {
    c: d.get("engine", "") for c, d in INDY500_ONLY_DRIVERS.items()
}

# Latent pace — used ONLY by the synthetic results generator, never the predictor.
_TRUTH_PACE: dict[str, float] = {c: p for (c, _, _, _, p) in _ROSTER}

# --------------------------------------------------------------------------- #
# Regulation eras — the IndyCar analog of motorsport_core.era.ERAS (core ships
# F1's table, so the boundary seasons live here and model.py applies the same
# hard-cut semantics). The DW12 chassis spans the whole curated window
# (2012-present); the meaningful cut is the 2020 aeroscreen (weight/CG/handling
# change). Both eras stay within one boundary of each other, so the full
# 2012+ curated history feeds the Elo priors with the inter-season shrink
# handling the drift.
# --------------------------------------------------------------------------- #
INDYCAR_ERAS: tuple[tuple[str, int, int | None], ...] = (
    ("dw12", 2012, 2019),         # DW12: original + aero-kit + universal-kit years
    ("aeroscreen", 2020, None),   # DW12 + aeroscreen
)

# ML training window: the learned regressors see recent-regulation seasons
# only (2019+ — the universal-aerokit/aeroscreen window); earlier seasons feed
# the Elo / era priors exclusively.
ML_FIRST_SEASON = 2019
# Elo seed window: the full curated history replays into the rating stack.
ELO_FIRST_SEASON = 2012
# Committed per-season history files go back to the DW12 introduction.
HISTORY_FIRST_SEASON = 2012

# --------------------------------------------------------------------------- #
# IndyCar model parameters — the tuning knobs of the model (see model.py).
#
# IndyCar is a spec series (DW12) with two engine manufacturers and multi-car
# teams: driver skill dominates, the team effect is real (dampers/engineering)
# and the engine adds a smaller shared effect. The DUAL track Elo (oval vs
# road/street) is the dominant split — an oval ace and a street specialist are
# different competitors, and the calendar alternates between the two worlds.
# --------------------------------------------------------------------------- #

# Pace scale (a seconds-like proxy the Plackett-Luce sampler reads; lower = faster).
PACE_BASE = 90.0
PACE_SPREAD = 0.50

# Blend weights for the latent skill (relative; need not sum to 1).
SKILL_WEIGHTS = {
    "elo": 0.40,        # overall driver Elo (all track types)
    "track_elo": 0.50,  # DUAL oval / road-street Elo for this round's group (dominant)
    "history": 0.35,    # smoothed current-season finishing history
    "team": 0.15,       # racing-team Elo (equipment / engineering)
    "engine": 0.10,     # engine-manufacturer Elo (Chevrolet / Honda)
    "ml": 0.50,         # optional gradient-boosted signal (ml_skill.py)
}

# Post-quali: when the REAL starting grid is known, the forecast conditions on
# it with a per-slot pace cost. IndyCar grids are informative (street courses
# especially — passing is hard), so the weight is meaningful. Checked on the
# 2026 walk-forward post-quali replay against the gridOrder baseline.
GRID_WEIGHT = 0.15

# A driver with fewer than this many prior IndyCar starts (across the Elo
# window) is treated as a rookie (pooled toward the team mean by the Elo prior).
ROOKIE_RACE_THRESHOLD = 5

# Monte Carlo sample count for the per-round probability + championship layers.
DEFAULT_SAMPLES = 4000

# --------------------------------------------------------------------------- #
# DNF / attrition head — a first-class component. IndyCar classifies every
# car (retirees keep a finishing position) and oval attrition runs well above
# road/street (pack racing, walls), so the race forecast COMPOSES a per-driver
# hazard with the pace model: sample DNFs first, rank the survivors, send
# retirees to the back — the NASCAR/F1-candidate composition pattern.
# --------------------------------------------------------------------------- #
DNF_BASE_RATE_PRIOR = 0.12   # long-run IndyCar attrition prior (per start)
DNF_PRIOR_STRENGTH = 60.0    # starts of pseudo-evidence behind the base prior
DNF_K_DRIVER = 12.0          # shrinkage strength for per-driver hazard
DNF_TRACK_BLEND = 0.55       # weight on track-type attrition vs season base
DNF_DRIVER_BLEND = 0.45      # weight on the driver hazard in the final mix
DNF_CLIP = (0.02, 0.45)      # per-driver hazard bounds

# Opt-in gradient-boosted skill regressor (indycar_predictions.ml_skill). ON
# by default but conservatively weighted; degrades silently to the Elo+history
# blend when deps/data are missing.
USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 3
ML_MIN_TRAIN_ROWS = 12
ML_MIN_SPLIT_ROWS = 24

# --------------------------------------------------------------------------- #
# Real data + calibration.
# --------------------------------------------------------------------------- #
MIN_REAL_ROUNDS_FOR_CALIBRATION = 6

# --------------------------------------------------------------------------- #
# Scraper validation (see sources/indycar_scraper_source.py + refresh.py).
# A normal 2026 IndyCar field is 25-27 cars; the Indy 500 runs 33 (allow a
# withdrawn-entry band). A parse outside these bands is refused, never
# ingested. The roster whitelist demands most of a classification's codes be
# known to config (roster + Indy-500-only) — a page for some other series or a
# vandalised table fails it.
# --------------------------------------------------------------------------- #
EXPECTED_CAR_COUNT = (24, 28)
INDY500_CAR_COUNT = (30, 35)
ROSTER_WHITELIST_MIN_FRACTION = 0.8

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
INDYCAR_USER_AGENT = (
    "motorsportverse/1.0 (IndyCar refresh; contact shenorrlab@technion.ac.il)"
)
