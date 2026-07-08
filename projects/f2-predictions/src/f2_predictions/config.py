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

import json
import os
from pathlib import Path

from motorsport_data.schema import Team, Venue

SPORT = "Formula 2"

# --------------------------------------------------------------------------- #
# Season selection (multi-season rollover support — see season_rollover.py).
#
# The literal tables below describe the 2026 season. A future season becomes
# active when ``season_rollover.py --start`` drops a marker file
# (``data/active_season.json``) after ``bootstrap_next_season.py`` has written
# an announced-calendar file (``data/announced_seasons/<year>.json``) — the F2
# analog of F1's ``generated_seasons/<year>.json`` (F2 calendars are announced
# late, so the bootstrap carries the current season forward as a placeholder
# until the real calendar lands). With no marker and no ``F2_SEASON_YEAR`` env
# override, this module behaves exactly as it always has (the 2026 literals).
# --------------------------------------------------------------------------- #
_DEFAULT_SEASON = 2026
# ``F2_DATA_DIR`` is a test seam only; unset in production.
_DATA_DIR = Path(os.environ.get("F2_DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = os.environ.get("F2_SEASON_YEAR", "").strip()
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
        f"F2 season {SEASON} is active but data/announced_seasons/{SEASON}.json is missing or "
        "invalid — run `python -m f2_predictions.bootstrap_next_season` first."
    )

# --------------------------------------------------------------------------- #
# Calendar — the official 2026 FIA Formula 2 schedule (14 rounds), verified
# against fiaformula2.com round titles and the 2026 F2 Championship calendar.
# Keys match circuits.json / lib/raceArt.ts venue keys. Round order is the
# official order (fly-aways Miami/Montréal are rounds 2-3, not appended late).
# --------------------------------------------------------------------------- #
CALENDAR: list[Venue] = [
    Venue(key="melbourne", name="Australia", country="Australia"),
    Venue(key="miami", name="Miami", country="USA"),
    Venue(key="montreal", name="Canada", country="Canada"),
    Venue(key="monaco", name="Monaco", country="Monaco"),
    Venue(key="catalunya", name="Spain", country="Spain"),
    Venue(key="spielberg", name="Austria", country="Austria"),
    Venue(key="silverstone", name="Great Britain", country="United Kingdom"),
    Venue(key="spa", name="Belgium", country="Belgium"),
    Venue(key="hungaroring", name="Hungary", country="Hungary"),
    Venue(key="monza", name="Italy", country="Italy"),
    Venue(key="madrid", name="Spain (Madrid)", country="Spain"),
    Venue(key="baku", name="Azerbaijan", country="Azerbaijan"),
    Venue(key="losail", name="Qatar", country="Qatar"),
    Venue(key="yas-marina", name="Abu Dhabi", country="UAE"),
]

# Per-round metadata (city + the official weekend dates). The feature date is the
# Sunday; a round is "completed" once its results are published (the data layer
# derives completion from the feed, not from the wall clock — see export.py).
CALENDAR_META: dict[int, dict[str, str]] = {
    1: {"city": "Melbourne", "sprint": "2026-03-07", "feature": "2026-03-08"},
    2: {"city": "Miami", "sprint": "2026-05-02", "feature": "2026-05-03"},
    3: {"city": "Montréal", "sprint": "2026-05-23", "feature": "2026-05-24"},
    4: {"city": "Monte Carlo", "sprint": "2026-06-06", "feature": "2026-06-07"},
    5: {"city": "Barcelona", "sprint": "2026-06-13", "feature": "2026-06-14"},
    6: {"city": "Spielberg", "sprint": "2026-06-27", "feature": "2026-06-28"},
    7: {"city": "Silverstone", "sprint": "2026-07-04", "feature": "2026-07-05"},
    8: {"city": "Spa-Francorchamps", "sprint": "2026-07-18", "feature": "2026-07-19"},
    9: {"city": "Budapest", "sprint": "2026-07-25", "feature": "2026-07-26"},
    10: {"city": "Monza", "sprint": "2026-09-05", "feature": "2026-09-06"},
    11: {"city": "Madrid", "sprint": "2026-09-12", "feature": "2026-09-13"},
    12: {"city": "Baku", "sprint": "2026-09-25", "feature": "2026-09-26"},
    13: {"city": "Lusail", "sprint": "2026-11-28", "feature": "2026-11-29"},
    14: {"city": "Yas Island", "sprint": "2026-12-05", "feature": "2026-12-06"},
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
# snapshot (data/official_2026.json) so one `python -m f2_predictions.refresh`
# advances the whole pipeline; falls back to a literal if the snapshot is absent.
# The synthetic generator also fabricates exactly this many rounds, so synthetic
# and real modes agree on which rounds are complete.
def _completed_from_snapshot(default: int = 5) -> int:
    snap_path = _DATA_DIR / f"official_{SEASON}.json"
    try:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        if snap.get("season") == SEASON and "completedRounds" in snap:
            return int(snap["completedRounds"])
    except Exception:
        pass
    return default


# A freshly started (announced) season has no snapshot yet — 0 rounds complete.
COMPLETED_ROUNDS = _completed_from_snapshot(default=5 if SEASON == _DEFAULT_SEASON else 0)

# --------------------------------------------------------------------------- #
# Teams (constructor-equivalent).
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="AIX Racing", color="#C0392B"),
    Team(name="ART Grand Prix", color="#5A5A5A"),
    Team(name="Campos Racing", color="#1F3A93"),
    Team(name="DAMS Lucas Oil", color="#0090D0"),
    Team(name="Hitech TGR", color="#D4123A"),
    Team(name="Invicta Racing", color="#8E44AD"),
    Team(name="MP Motorsport", color="#F47C20"),
    Team(name="PREMA Racing", color="#E2001A"),
    Team(name="Rodin Motorsport", color="#00A19A"),
    Team(name="TRIDENT", color="#0050A0"),
    Team(name="Van Amersfoort Racing", color="#FF5A00"),
]

# Some official pages abbreviate team names (F3's standings say "Hitech" for
# "Hitech TGR"). F2's pages currently match config.TEAMS verbatim, so this is
# empty — it exists so refresh.py normalises through one seam, F3-parity.
TEAM_ALIASES: dict[str, str] = {}

if _ANNOUNCED and _ANNOUNCED.get("teams"):
    TEAMS = [Team(name=t["name"], color=t.get("color", "#888888")) for t in _ANNOUNCED["teams"]]

# --------------------------------------------------------------------------- #
# Driver roster — code, full name, team. Two per team (22-car grid).
# --------------------------------------------------------------------------- #
# (code, name, team, latent_pace)  — lower latent_pace = faster (seconds proxy).
_ROSTER: list[tuple[str, str, str, float]] = [
    ("MIN", "Gabriele Minì", "MP Motorsport", 89.32),
    ("DUN", "Alex Dunne", "Rodin Motorsport", 89.40),
    ("LEO", "Noel León", "Campos Racing", 89.51),
    ("CAM", "Rafael Câmara", "Invicta Racing", 89.59),
    ("TSO", "Nikola Tsolov", "Campos Racing", 89.61),
    ("BEG", "Dino Beganovic", "DAMS Lucas Oil", 89.62),
    ("STE", "Martinius Stenshorne", "Rodin Motorsport", 89.76),
    ("MAI", "Kush Maini", "ART Grand Prix", 89.77),
    ("VAN", "Laurens van Hoepen", "TRIDENT", 89.86),
    ("INT", "Tasanapol Inthraphuvasak", "ART Grand Prix", 89.94),
    ("MIY", "Ritomo Miyata", "Hitech TGR", 89.94),
    ("DUR", "Joshua Dürksen", "Invicta Racing", 89.96),
    ("MON", "Sebastián Montoya", "PREMA Racing", 90.01),
    ("BIL", "Roman Bilinski", "DAMS Lucas Oil", 90.07),
    ("GOE", "Oliver Goethe", "MP Motorsport", 90.12),
    ("HER", "Cian Herta", "Hitech TGR", 90.15),
    ("FIT", "Enzo Fittipaldi", "AIX Racing", 90.33),
    ("VAR", "Nicola Varrone", "Van Amersfoort Racing", 90.36),
    ("BOY", "Mari Boya", "PREMA Racing", 90.43),
    ("BEN", "John Bennett", "TRIDENT", 90.52),
    ("VIL", "Rafael Villagómez", "Van Amersfoort Racing", 90.53),
    ("SHI", "Callum Shields", "AIX Racing", 90.82),
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

# Feature race: when REAL qualifying is known (post-quali), the forecast conditions
# on the actual grid. Track position matters in the feature too — pole is a genuine
# advantage — but far less than in the reverse-grid sprint, because the feature grid
# is already merit-aligned and F2 features are overtaking-heavy. A gentle per-slot
# pace cost nudges the forecast toward the real grid without overpowering skill.
# Unused until a real qualifying order is supplied (pre-quali keeps pure-pace merit).
FEATURE_GRID_WEIGHT = 0.05  # seconds of pace cost per feature grid slot back

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
