"""F2-specific configuration: calendar, roster, teams, and points systems.

F2 runs on F1 weekends at shared circuits with a two-race format (Saturday
sprint + Sunday feature). This module is the only F2-domain knowledge the
project carries; everything else is reused from motorsport-core / motorsport-data.

Results data: F2 is not served by Jolpica/Ergast and FastF1's F2 coverage is
partial, so until a live feed is wired (see ``datasource.py``) the project runs
on a **reproducible latent-pace model** (`_TRUTH_PACE`) that generates
deterministic, realistic results. This keeps the full pipeline functional and
testable end-to-end; the predictor never sees `_TRUTH_PACE` — it estimates pace
from prior results only (leakage-safe).
"""
from __future__ import annotations

from motorsport_data.schema import Team, Venue

SPORT = "Formula 2"
SEASON = 2026

# --------------------------------------------------------------------------- #
# Calendar — shared F1 circuits used as F2 support rounds.
# --------------------------------------------------------------------------- #
CALENDAR: list[Venue] = [
    Venue(key="sakhir", name="Bahrain", country="Bahrain"),
    Venue(key="jeddah", name="Saudi Arabia", country="Saudi Arabia"),
    Venue(key="melbourne", name="Australia", country="Australia"),
    Venue(key="imola", name="Emilia-Romagna", country="Italy"),
    Venue(key="monaco", name="Monaco", country="Monaco"),
    Venue(key="catalunya", name="Spain", country="Spain"),
    Venue(key="spielberg", name="Austria", country="Austria"),
    Venue(key="silverstone", name="Great Britain", country="United Kingdom"),
    Venue(key="hungaroring", name="Hungary", country="Hungary"),
    Venue(key="spa", name="Belgium", country="Belgium"),
    Venue(key="monza", name="Italy", country="Italy"),
    Venue(key="baku", name="Azerbaijan", country="Azerbaijan"),
    Venue(key="yas-marina", name="Abu Dhabi", country="UAE"),
]

# How many rounds are "in the books" — the rest are upcoming (predicted).
COMPLETED_ROUNDS = 7

# --------------------------------------------------------------------------- #
# Teams (constructor-equivalent).
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="ART Grand Prix", color="#3B3B3B"),
    Team(name="Prema Racing", color="#E2001A"),
    Team(name="MP Motorsport", color="#F47C20"),
    Team(name="DAMS", color="#0090D0"),
    Team(name="Campos Racing", color="#1F3A93"),
    Team(name="Invicta Racing", color="#8E44AD"),
    Team(name="Hitech", color="#101820"),
    Team(name="Rodin Motorsport", color="#00A19A"),
    Team(name="Van Amersfoort Racing", color="#FF5A00"),
    Team(name="Trident", color="#0050A0"),
    Team(name="AIX Racing", color="#C0392B"),
]

# --------------------------------------------------------------------------- #
# Driver roster — code, full name, team. Two per team (22-car grid).
# --------------------------------------------------------------------------- #
# (code, name, team, latent_pace)  — lower latent_pace = faster (seconds proxy).
_ROSTER: list[tuple[str, str, str, float]] = [
    ("MAR", "Andrea Kimi Antonelli", "Prema Racing", 89.20),
    ("HAD", "Isack Hadjar", "Campos Racing", 89.35),
    ("BOR", "Gabriel Bortoleto", "Invicta Racing", 89.28),
    ("MAI", "Zane Maloney", "Rodin Motorsport", 89.55),
    ("CRA", "Jak Crawford", "DAMS", 89.60),
    ("ARO", "Paul Aron", "Hitech", 89.62),
    ("VES", "Richard Verschoor", "Trident", 89.70),
    ("HAU", "Roman Stanek", "Trident", 89.95),
    ("FOR", "Oliver Goethe", "MP Motorsport", 89.75),
    ("VID", "Dennis Hauger", "MP Motorsport", 89.50),
    ("COR", "Joshua Duerksen", "AIX Racing", 90.10),
    ("BEN", "Amaury Cordeel", "Hitech", 90.20),
    ("MAS", "Pepe Marti", "Campos Racing", 89.85),
    ("FIT", "Kush Maini", "DAMS", 89.90),
    ("LEC", "Enzo Fittipaldi", "Van Amersfoort Racing", 90.05),
    ("BRO", "Taylor Barnard", "AIX Racing", 89.80),
    ("STA", "Victor Martins", "ART Grand Prix", 89.45),
    ("NAK", "Sami Meguetounif", "ART Grand Prix", 90.15),
    ("VAR", "Ritomo Miyata", "Rodin Motorsport", 90.25),
    ("COL", "Franco Colapinto", "Van Amersfoort Racing", 89.65),
    ("IWA", "Rafael Villagomez", "Invicta Racing", 90.30),
    ("DUR", "John Bennett", "Prema Racing", 90.00),
]

DRIVERS: list[dict[str, str]] = [
    {"code": c, "name": n, "team": t} for (c, n, t, _) in _ROSTER
]
TEAM_OF: dict[str, str] = {c: t for (c, _, t, _) in _ROSTER}
DRIVER_NAME: dict[str, str] = {c: n for (c, n, _, _) in _ROSTER}

# Latent pace — used ONLY by the synthetic results generator, never the predictor.
_TRUTH_PACE: dict[str, float] = {c: p for (c, _, _, p) in _ROSTER}

# --------------------------------------------------------------------------- #
# Points systems (standard F2).
# --------------------------------------------------------------------------- #
FEATURE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
SPRINT_POINTS = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
POLE_POINTS = 2          # feature-race pole
FASTEST_LAP_POINTS = 1   # if classified in the top 10

# --------------------------------------------------------------------------- #
# F2 model parameters — the tuning knobs of the unique F2 model (see model.py).
#
# F2 is a *spec series*: identical machinery means driver skill dominates and the
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
# is what gives the F2 sprint its high-variance, overtaking-heavy character.
REVERSE_GRID_SIZE = 10     # F2 reverses the top 10 of the feature-quali order
SPRINT_GRID_PENALTY = 0.12  # seconds of pace cost per grid slot started back

# A driver with fewer than this many prior race entries is treated as a rookie
# (pooled toward the team mean by the Elo prior; used as a calibration stratum).
ROOKIE_RACE_THRESHOLD = 3

# Monte Carlo sample count for the per-round probability + championship layers.
DEFAULT_SAMPLES = 4000

# Opt-in Bayesian hierarchical skill prior (motorsport_core.hierarchical_bayes).
# Off by default: PyMC is an optional, slow dependency and CI must stay
# deterministic. When enabled and PyMC is importable the model folds the
# driver-within-team posterior into the blend; otherwise it degrades to Elo +
# history with no error (mirrors the F1 optional-LSTM pattern).
USE_BAYESIAN_SKILL = False

# Opt-in gradient-boosted skill regressor (f2_predictions.ml_skill) — the
# F1-parity ensemble signal. ON by default but conservatively weighted: it folds
# a learned GBR+XGB mapping from a richer prior-round feature vector into the
# blend whenever scikit-learn/xgboost are importable and there is enough prior
# data. It degrades silently to the Elo+history blend when the deps are missing,
# there is too little data, or training fails — never breaking a forecast. The
# weight is deliberately small on the synthetic source (where the linear blend
# already saturates accuracy); it becomes load-bearing once real F2 results give
# the trees feature interactions to exploit.
USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 2     # need >= 2 prior rounds so features have variance / a trend
ML_MIN_TRAIN_ROWS = 8       # minimum raced-driver rows before a fit is trustworthy
ML_MIN_SPLIT_ROWS = 12      # below this, score weights in-sample instead of splitting

# Per-lap Monte-Carlo race simulator (f2_predictions.train_race_pace) — a ready
# seam, DORMANT today. F2 lap-by-lap telemetry is not available from any wired
# source, so this stays OFF and the model uses the Plackett-Luce ordering. When a
# lap feed lands (datasource gains a ``lap_data_for_round`` hook), flip this on and
# the GBR+XGB lap-time ensemble + simulator activate without further plumbing.
# Mirrors the F1 flagship's ``--use-race-simulator`` opt-in.
USE_RACE_SIMULATOR = False

# --------------------------------------------------------------------------- #
# Phase 2 — real data feed + calibration.
#
# Results are selected at runtime (see datasource.py): the deterministic
# synthetic source by default, or a real-feed composite when the environment
# variable ``F2_USE_LIVE_RESULTS=1`` is set. Probability calibration only turns
# on once enough *real* (non-synthetic) rounds have been observed — the honest
# gate that keeps the website from claiming calibration it hasn't earned.
# --------------------------------------------------------------------------- #
MIN_REAL_ROUNDS_FOR_CALIBRATION = 4

# Optional official FIA F2 results URL template (used only when
# F2_ENABLE_OFFICIAL_FETCH=1). Empty = the official source is disabled.
OFFICIAL_F2_RESULTS_URL = ""

# --------------------------------------------------------------------------- #
# Real feed — fiaformula2.com scraper (see sources/fia_f2_source.py).
#
# The official site serves per-round results as server-rendered HTML at
# /Results?raceid=N, including a 3-letter driver code and team per row, plus a
# round navigator listing every raceid in the season. We only need one anchor
# raceid per season; the scraper derives the rest from the navigator.
# --------------------------------------------------------------------------- #
FIA_F2_BASE_URL = "https://www.fiaformula2.com"

# season -> any one raceid in that season (the scraper expands to all rounds).
FIA_F2_SEASON_ANCHORS: dict[int, int] = {
    2024: 1064,  # Round 1 Bahrain (… 1076 = R13 Qatar, 1077 = R14 Abu Dhabi)
    2026: 1092,  # Round 1 Australia
}
