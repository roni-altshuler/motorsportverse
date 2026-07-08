"""F3-specific configuration: calendar, roster, teams, and points systems.

F3 runs on F1 weekends at shared circuits with a two-race format (Saturday
sprint + Sunday feature). This module is the only F3-domain knowledge the
project carries; everything else is reused from motorsport-core / motorsport-data.

Results data: F3 is not served by Jolpica/Ergast, but fiaformula3.com runs the
same CMS as F2's fiaformula2.com, so the shared ``FiaFeederSource`` scraper
works unchanged (see ``sources/fia_f3_source.py``). The committed snapshot
(``data/official_2026.json``) carries the real season; the **reproducible
latent-pace model** (`_TRUTH_PACE`) remains as the deterministic offline
fallback that keeps the pipeline functional and testable end-to-end. The
predictor never sees `_TRUTH_PACE` — it estimates pace from prior results only
(leakage-safe).

The 2026 sporting facts below (points tables, reverse-grid size) were verified
against fiaformula3.com round pages + official standings breakdowns, not
assumed from prior seasons.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from motorsport_data.schema import Team, Venue

SPORT = "Formula 3"

# --------------------------------------------------------------------------- #
# Season selection (multi-season rollover support — see season_rollover.py).
#
# The literal tables below describe the 2026 season. A future season becomes
# active when ``season_rollover.py --start`` drops a marker file
# (``data/active_season.json``) after ``bootstrap_next_season.py`` has written
# an announced-calendar file (``data/announced_seasons/<year>.json``) — the F3
# analog of F1's ``generated_seasons/<year>.json`` (F3 calendars are announced
# late, so the bootstrap carries the current season forward as a placeholder
# until the real calendar lands). With no marker and no ``F3_SEASON_YEAR`` env
# override, this module behaves exactly as it always has (the 2026 literals).
# --------------------------------------------------------------------------- #
_DEFAULT_SEASON = 2026
# ``F3_DATA_DIR`` is a test seam only; unset in production.
_DATA_DIR = Path(os.environ.get("F3_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("F3_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


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
        f"F3 season {SEASON} is active but data/announced_seasons/{SEASON}.json is missing or "
        "invalid — run `python -m f3_predictions.bootstrap_next_season` first."
    )

# --------------------------------------------------------------------------- #
# Calendar — the official 2026 FIA Formula 3 schedule (9 rounds after the
# Sakhir round was cancelled), verified against fiaformula3.com round titles.
# Keys match circuits.json / lib/raceArt.ts venue keys.
# --------------------------------------------------------------------------- #
CALENDAR: list[Venue] = [
    Venue(key="melbourne", name="Australia", country="Australia"),
    Venue(key="monaco", name="Monaco", country="Monaco"),
    Venue(key="catalunya", name="Spain", country="Spain"),
    Venue(key="spielberg", name="Austria", country="Austria"),
    Venue(key="silverstone", name="Great Britain", country="United Kingdom"),
    Venue(key="spa", name="Belgium", country="Belgium"),
    Venue(key="hungaroring", name="Hungary", country="Hungary"),
    Venue(key="monza", name="Italy", country="Italy"),
    Venue(key="madrid", name="Spain (Madrid)", country="Spain"),
]

# Per-round metadata (city + the official weekend dates). The feature date is the
# Sunday; a round is "completed" once its results are published (the data layer
# derives completion from the feed, not from the wall clock — see export.py).
CALENDAR_META: dict[int, dict[str, str]] = {
    1: {"city": "Melbourne", "sprint": "2026-03-07", "feature": "2026-03-08"},
    2: {"city": "Monte Carlo", "sprint": "2026-06-06", "feature": "2026-06-07"},
    3: {"city": "Barcelona", "sprint": "2026-06-13", "feature": "2026-06-14"},
    4: {"city": "Spielberg", "sprint": "2026-06-27", "feature": "2026-06-28"},
    5: {"city": "Silverstone", "sprint": "2026-07-04", "feature": "2026-07-05"},
    6: {"city": "Spa-Francorchamps", "sprint": "2026-07-18", "feature": "2026-07-19"},
    7: {"city": "Budapest", "sprint": "2026-07-25", "feature": "2026-07-26"},
    8: {"city": "Monza", "sprint": "2026-09-05", "feature": "2026-09-06"},
    9: {"city": "Madrid", "sprint": "2026-09-12", "feature": "2026-09-13"},
}

# Announced (post-2026) seasons override the literal calendar from the payload
# written by bootstrap_next_season.py / a human-installed announced calendar.
if _ANNOUNCED:
    CALENDAR = [
        Venue(key=e["key"], name=e["name"], country=e["country"])
        for e in _ANNOUNCED["calendar"]
    ]
    CALENDAR_META = {
        int(e.get("round", i)): {
            "city": e.get("city", ""),
            "sprint": e.get("sprint", ""),
            "feature": e.get("feature", ""),
        }
        for i, e in enumerate(_ANNOUNCED["calendar"], start=1)
    }

# How many rounds are "in the books". Derived from the committed real-data
# snapshot (data/official_2026.json) so one `python -m f3_predictions.refresh`
# advances the whole pipeline; falls back to a literal if the snapshot is absent.
# The synthetic generator also fabricates exactly this many rounds, so synthetic
# and real modes agree on which rounds are complete.
def _completed_from_snapshot(default: int = 4) -> int:
    snap_path = _DATA_DIR / f"official_{SEASON}.json"
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        if snap.get("season") == SEASON and "completedRounds" in snap:
            return int(snap["completedRounds"])
    except Exception:
        pass
    return default


# A freshly started (announced) season has no snapshot yet — 0 rounds complete.
COMPLETED_ROUNDS = _completed_from_snapshot(default=4 if SEASON == _DEFAULT_SEASON else 0)

# --------------------------------------------------------------------------- #
# Teams (constructor-equivalent) — the ten 2026 FIA Formula 3 entrants.
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="AIX Racing", color="#C0392B"),
    Team(name="ART Grand Prix", color="#5A5A5A"),
    Team(name="Campos Racing", color="#1F3A93"),
    Team(name="DAMS Lucas Oil", color="#0090D0"),
    Team(name="Hitech TGR", color="#D4123A"),
    Team(name="MP Motorsport", color="#F47C20"),
    Team(name="PREMA Racing", color="#E2001A"),
    Team(name="Rodin Motorsport", color="#00A19A"),
    Team(name="TRIDENT", color="#0050A0"),
    Team(name="Van Amersfoort Racing", color="#FF5A00"),
]

# Some official pages abbreviate team names (e.g. the standings table says
# "Hitech" while entry lists say "Hitech TGR"). Normalise to the TEAMS names.
TEAM_ALIASES: dict[str, str] = {
    "Hitech": "Hitech TGR",
}

if _ANNOUNCED and _ANNOUNCED.get("teams"):
    TEAMS = [Team(name=t["name"], color=t.get("color", "#888888")) for t in _ANNOUNCED["teams"]]

# --------------------------------------------------------------------------- #
# Driver roster — code, name, team. Three per team (30-car grid), as raced at
# the most recent completed round (mid-season seat changes replace the earlier
# occupant; the standings keep departed drivers, the roster is who races NOW).
# --------------------------------------------------------------------------- #
# (code, name, team, latent_pace)  — lower latent_pace = faster (seconds proxy).
_ROSTER: list[tuple[str, str, str, float]] = [
    ("UGO", "U. Ugochukwu", "Campos Racing", 89.30),
    ("SLA", "F. Slater", "TRIDENT", 89.42),
    ("NAE", "T. Naël", "Campos Racing", 89.50),
    ("BDE", "B. Del Pino", "Van Amersfoort Racing", 89.55),
    ("STR", "N. Strømsted", "TRIDENT", 89.60),
    ("BAD", "B. Badoer", "Rodin Motorsport", 89.62),
    ("CLE", "P. Clerot", "Rodin Motorsport", 89.70),
    ("YAM", "H. Yamakoshi", "Van Amersfoort Racing", 89.72),
    ("KAT", "T. Kato", "ART Grand Prix", 89.78),
    ("EDE", "E. Deligny", "Van Amersfoort Racing", 89.82),
    ("RIV", "E. Rivera", "Campos Racing", 89.86),
    ("NAK", "J. Nakamura", "Hitech TGR", 89.88),
    ("XIE", "G. Xie", "DAMS Lucas Oil", 89.95),
    ("WHA", "J. Wharton", "PREMA Racing", 89.97),
    ("TAP", "T. Taponen", "MP Motorsport", 90.00),
    ("GLA", "M. Gładysz", "ART Grand Prix", 90.05),
    ("GIU", "A. Giusti", "MP Motorsport", 90.10),
    ("LE", "K. Le", "ART Grand Prix", 90.25),
    ("LAC", "N. Lacorte", "DAMS Lucas Oil", 90.30),
    ("SHA", "L. Sharp", "PREMA Racing", 90.35),
    ("COL", "M. Colnaghi", "MP Motorsport", 90.38),
    ("GAR", "J. Garfias", "PREMA Racing", 90.42),
    ("BHI", "N. Bhirombhakdi", "DAMS Lucas Oil", 90.50),
    ("MCL", "F. McLaughlin", "Hitech TGR", 90.55),
    ("DEP", "M. De Palo", "TRIDENT", 90.58),
    ("HO", "C. Ho", "Rodin Motorsport", 90.62),
    ("BAR", "F. Barrichello", "AIX Racing", 90.68),
    ("SHI", "W. Shin", "Hitech TGR", 90.75),
    ("HAN", "S. Hanna", "AIX Racing", 90.80),
    ("DAV", "Y. David", "AIX Racing", 90.85),
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

# Drivers replaced mid-season. They are not on the current roster but appear in
# early-round classifications and the official standings, so the team-points
# aggregation still needs their team mapping (else their points silently vanish
# from recomputed team standings).
FORMER_DRIVERS: dict[str, dict[str, str]] = {
    "BEN": {"name": "B. Benavides", "team": "AIX Racing"},
    "ESC": {"name": "R. Escotto", "team": "AIX Racing"},
    "HEU": {"name": "P. Heuzenroeder", "team": "Campos Racing"},
    "CAR": {"name": "J. Carrasquedo", "team": "AIX Racing"},
}

# The 2026 mid-season changes don't carry into a future announced season.
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
# Points systems — 2026 FIA Formula 3, verified against the official standings
# score breakdown: feature 25-18-15-12-10-8-6-4-2-1, sprint 10-9-8-7-6-5-4-3-2-1
# (a shortened sprint pays half points, handled by the official feed, not here).
# --------------------------------------------------------------------------- #
FEATURE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
SPRINT_POINTS = {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}
POLE_POINTS = 2          # feature-race pole
FASTEST_LAP_POINTS = 1   # if classified in the top 10

# --------------------------------------------------------------------------- #
# F3 model parameters — the tuning knobs of the unique F3 model (see model.py).
#
# F3 is a *spec series*: identical machinery means driver skill dominates and the
# team effect is minor, the opposite weighting from F1. The model blends three
# leakage-safe driver signals into a per-driver "pace" the calibration sampler
# consumes (lower = faster), then routes it through two race-type heads — a merit
# feature race and a reverse-grid sprint.
# --------------------------------------------------------------------------- #

# Pace scale (a seconds-like proxy the Plackett-Luce sampler reads; lower = faster).
PACE_BASE = 90.0           # neutral pace when there is no signal yet
PACE_SPREAD = 0.55         # seconds per unit of blended-skill z-score

# Blend weights for the latent skill (relative; need not sum to 1). Driver-level
# signals (elo, finishing history) dominate; the team component is deliberately
# small because the spec chassis flattens constructor variance. ``ml`` weights the
# optional gradient-boosted regressor (see ``ml_skill.py``); ``bayes`` weights the
# optional PyMC posterior. Both are folded in only when their signal is available.
SKILL_WEIGHTS = {"elo": 0.55, "history": 0.45, "team": 0.12, "ml": 0.5, "bayes": 0.5}

# Reverse-grid sprint: the sprint grid is the feature-quali top-N reversed. The
# grid penalty makes a fast driver starting at the back have to overtake, which
# is what gives the F3 sprint its high-variance, overtaking-heavy character.
# N=12 verified from 2026 rounds (quali P12 starts the sprint on pole).
REVERSE_GRID_SIZE = 12     # F3 reverses the top 12 of the feature-quali order
SPRINT_GRID_PENALTY = 0.12  # seconds of pace cost per grid slot started back

# Feature race: when REAL qualifying is known (post-quali), the forecast conditions
# on the actual grid. Track position matters in the feature too — pole is a genuine
# advantage — but far less than in the reverse-grid sprint, because the feature grid
# is already merit-aligned and F3 features are overtaking-heavy. A gentle per-slot
# pace cost nudges the forecast toward the real grid without overpowering skill.
# Unused until a real qualifying order is supplied (pre-quali keeps pure-pace merit).
FEATURE_GRID_WEIGHT = 0.05  # seconds of pace cost per feature grid slot back

# A driver with fewer than this many prior race entries is treated as a rookie
# (pooled toward the team mean by the Elo prior; used as a calibration stratum).
# F3 grids are rookie-heavy (most of the field debuts each season), so the pool
# is the norm rather than the exception.
ROOKIE_RACE_THRESHOLD = 3

# Monte Carlo sample count for the per-round probability + championship layers.
DEFAULT_SAMPLES = 4000

# Opt-in Bayesian hierarchical skill prior (motorsport_core.hierarchical_bayes).
# Off by default: PyMC is an optional, slow dependency and CI must stay
# deterministic. When enabled and PyMC is importable the model folds the
# driver-within-team posterior into the blend; otherwise it degrades to Elo +
# history with no error (mirrors the F1 optional-LSTM pattern).
USE_BAYESIAN_SKILL = False

# Opt-in gradient-boosted skill regressor (f3_predictions.ml_skill) — the
# F1-parity ensemble signal. ON by default but conservatively weighted: it folds
# a learned GBR+XGB mapping from a richer prior-round feature vector into the
# blend whenever scikit-learn/xgboost are importable and there is enough prior
# data. It degrades silently to the Elo+history blend when the deps are missing,
# there is too little data, or training fails — never breaking a forecast.
USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 2     # need >= 2 prior rounds so features have variance / a trend
ML_MIN_TRAIN_ROWS = 8       # minimum raced-driver rows before a fit is trustworthy
ML_MIN_SPLIT_ROWS = 12      # below this, score weights in-sample instead of splitting

# Per-lap Monte-Carlo race simulator (f3_predictions.train_race_pace) — a ready
# seam, DORMANT today. F3 lap-by-lap telemetry is not available from any wired
# source, so this stays OFF and the model uses the Plackett-Luce ordering. When a
# lap feed lands (datasource gains a ``lap_data_for_round`` hook), flip this on and
# the GBR+XGB lap-time ensemble + simulator activate without further plumbing.
# Mirrors the F1 flagship's ``--use-race-simulator`` opt-in.
USE_RACE_SIMULATOR = False

# --------------------------------------------------------------------------- #
# Real data feed + calibration.
#
# Results are selected at runtime (see datasource.py): the deterministic
# synthetic source by default, or a real-feed composite when the environment
# variable ``F3_USE_LIVE_RESULTS=1`` is set. Probability calibration only turns
# on once enough *real* (non-synthetic) rounds have been observed — the honest
# gate that keeps the website from claiming calibration it hasn't earned.
# --------------------------------------------------------------------------- #
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4

# Optional official FIA F3 results URL template (used only when
# F3_ENABLE_OFFICIAL_FETCH=1). Empty = the official source is disabled.
OFFICIAL_F3_RESULTS_URL = ""

# --------------------------------------------------------------------------- #
# Real feed — fiaformula3.com scraper (see sources/fia_f3_source.py).
#
# The official site serves per-round results as server-rendered HTML at
# /Results?raceid=N, including a 3-letter driver code and team per row, plus a
# round navigator listing every raceid in the season. We only need one anchor
# raceid per season; the scraper derives the rest from the navigator. The
# navigator also carries cancelled rounds (2026's Sakhir raceid 1070) — those
# pages have no round title, so the calendar parser skips them naturally.
# --------------------------------------------------------------------------- #
FIA_F3_BASE_URL = "https://www.fiaformula3.com"

# season -> any one raceid in that season (the scraper expands to all rounds).
FIA_F3_SEASON_ANCHORS: dict[int, int] = {
    2024: 1049,  # Round 1 Bahrain (… 1058 = R10)
    2025: 1059,  # Round 1 Australia (… 1068 = R10 Monza)
    2026: 1069,  # Round 1 Australia (1070 = cancelled Sakhir; … 1078 = R9 Madrid)
}
