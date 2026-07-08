"""NASCAR Cup Series sporting constants.

Currently: points tables and championship formats only. Calendar and roster
sections will be appended by later work — keep each section self-contained so
additions don't collide.

Format provenance (verified 2026-07-07)
---------------------------------------
NASCAR announced in January 2026 that the 2014-2025 elimination playoffs are
**gone**: the Cup Series returns to a Chase-style championship for 2026
(nascar.com 2026-01-12 "NASCAR returns to Chase championship format for 2026";
en.wikipedia.org/wiki/2026_NASCAR_Cup_Series). Verified 2026 rules:

* 26-race regular season, then a 10-race Chase (36 points races total).
* Top **16 on points** qualify — the win-and-you're-in rule is scrapped.
* Chase points reset is **staggered by regular-season seed**: 2100 for the
  regular-season champion (a 25-point premium), 2075 for the 2nd seed, 2065
  for the 3rd, then -5 per seed down to 2000 for the 16th seed.
* **No eliminations and no playoff points.** Most points after race 36 wins.
* Race winner's points raised from 40 to **55**; positions 2+ unchanged
  (35, 34, ... down to 1 at 36th and beyond). Stage racing continues
  (top-10 per stage score 10..1; the stage-win playoff point is gone along
  with all playoff points).

The 2017-2025 elimination format is kept here because we backtest on those
seasons: 16 drivers (win-and-in), Round of 16/12/8 (3 races each) cutting to
12/8/4 with resets 2000/3000/4000 + banked playoff points, a round race win
auto-advances, and a single-race Championship 4 at 5000 points where banked
playoff points do NOT apply — best finisher of the four is champion. Playoff
points: 5 per race win, 1 per stage win, and a regular-season top-10 bonus of
15 (champion), 10, 8, 7, 6, 5, 4, 3, 2, 1 (jayski.com 2024 playoffs guide;
nascar.com playoffs explainers).
"""
from __future__ import annotations

from .championship_playoffs import PlayoffFormat, PlayoffRound

# --------------------------------------------------------------------------- #
# Race points (1-based finishing position -> points)
# --------------------------------------------------------------------------- #

#: 2017-2025 Cup race points: winner 40, then 35, 34, ... decreasing by one to
#: 1 point at 36th; 37th-40th also score 1.
RACE_POINTS_2017_2025: dict[int, int] = {
    1: 40,
    **{p: 37 - p for p in range(2, 36)},  # 2nd = 35 ... 35th = 2
    **{p: 1 for p in range(36, 41)},
}

#: 2026 Cup race points: winner raised to 55; positions 2+ unchanged.
RACE_POINTS_2026: dict[int, int] = {**RACE_POINTS_2017_2025, 1: 55}

#: Stage points, unchanged since stages arrived in 2017: top 10 in each of the
#: two scored stages earn 10, 9, ... 1.
STAGE_POINTS: dict[int, int] = {p: 11 - p for p in range(1, 11)}
STAGES_PER_RACE: int = 2  # scored stages (the finish is the "final stage")

# --------------------------------------------------------------------------- #
# Playoff points (2017-2025 elimination era only — none exist in 2026)
# --------------------------------------------------------------------------- #

RACE_WIN_PLAYOFF_POINTS: int = 5
STAGE_WIN_PLAYOFF_POINTS: int = 1
#: Regular-season top-10 bonus: champion 15, then 10, 8, 7, 6, 5, 4, 3, 2, 1.
REGULAR_SEASON_PLAYOFF_POINTS: dict[int, int] = {
    1: 15, 2: 10, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1,
}

# --------------------------------------------------------------------------- #
# Championship formats
# --------------------------------------------------------------------------- #

REGULAR_SEASON_RACES: int = 26
PLAYOFF_FIELD_SIZE: int = 16

#: 2017-2025 elimination playoffs — the backtest format.
CUP_PLAYOFF_FORMAT_2017_2025 = PlayoffFormat(
    regular_season_races=REGULAR_SEASON_RACES,
    playoff_field_size=PLAYOFF_FIELD_SIZE,
    rounds=(
        PlayoffRound(
            key="round_of_16", name="Round of 16", n_races=3,
            advancing=12, base_points=2000,
        ),
        PlayoffRound(
            key="round_of_12", name="Round of 12", n_races=3,
            advancing=8, base_points=3000,
        ),
        PlayoffRound(
            key="round_of_8", name="Round of 8", n_races=3,
            advancing=4, base_points=4000,
        ),
        PlayoffRound(
            key="championship_4", name="Championship 4", n_races=1,
            advancing=None, base_points=5000,
            bank_playoff_points=False,  # the bank stops at the Round of 8
            winner_take_all=True,       # best finisher of the four is champion
        ),
    ),
    race_points=RACE_POINTS_2017_2025,
    stage_points=STAGE_POINTS,
    stages_per_race=STAGES_PER_RACE,
    qualification="wins_first",
    win_playoff_points=RACE_WIN_PLAYOFF_POINTS,
    stage_win_playoff_points=STAGE_WIN_PLAYOFF_POINTS,
    regular_season_playoff_points=REGULAR_SEASON_PLAYOFF_POINTS,
)

#: 2026 Chase seeding bonuses over the 2000 base, seeds 1..16:
#: 2100, 2075, 2065, then -5 per seed down to 2000.
CHASE_SEED_BONUS_2026: tuple[int, ...] = (100, 75) + tuple(range(65, -1, -5))

#: The format actually in force for 2026 (announced January 2026).
CUP_CHASE_FORMAT_2026 = PlayoffFormat(
    regular_season_races=REGULAR_SEASON_RACES,
    playoff_field_size=PLAYOFF_FIELD_SIZE,
    rounds=(
        PlayoffRound(
            key="the_chase", name="The Chase", n_races=10,
            advancing=None,             # no eliminations
            base_points=2000,
            seed_bonus=CHASE_SEED_BONUS_2026,
            bank_playoff_points=False,  # playoff points no longer exist
            win_advances=False,
            winner_take_all=False,      # most points after race 36 wins
        ),
    ),
    race_points=RACE_POINTS_2026,
    stage_points=STAGE_POINTS,
    stages_per_race=STAGES_PER_RACE,
    qualification="points",             # win-and-in scrapped
    win_playoff_points=0,
    stage_win_playoff_points=0,
    regular_season_playoff_points={},
)

#: Canonical elimination-playoff constant (the format the simulator was built
#: around and the one used for 2017-2025 backtests).
CUP_PLAYOFF_FORMAT: PlayoffFormat = CUP_PLAYOFF_FORMAT_2017_2025

#: The format in force for the season we are currently predicting.
CUP_CURRENT_FORMAT: PlayoffFormat = CUP_CHASE_FORMAT_2026

# --------------------------------------------------------------------------- #
# Calendar & roster — added by later work; keep new sections below this line.
# --------------------------------------------------------------------------- #

# Imports live mid-file by design: the calendar/roster section is appended
# below the original points/format tables per the module's marker contract.
import json as _json  # noqa: E402
import os as _os  # noqa: E402
import re as _re  # noqa: E402
import unicodedata as _unicodedata  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from motorsport_data.schema import Team, Venue  # noqa: E402

SPORT = "NASCAR"

# --------------------------------------------------------------------------- #
# Season selection (multi-season rollover support — see season_rollover.py).
#
# The literal tables below describe the 2026 Cup season. A future season
# becomes active when ``season_rollover.py --start`` drops a marker file
# (``data/active_season.json``) after ``bootstrap_next_season.py`` has written
# an announced-calendar file (``data/announced_seasons/<year>.json``). With no
# marker and no ``NASCAR_SEASON_YEAR`` env override, this module behaves
# exactly as it always has (the 2026 literals).
# --------------------------------------------------------------------------- #
_DEFAULT_SEASON = 2026
# ``NASCAR_DATA_DIR`` is a test seam only; unset in production.
_DATA_DIR = _Path(
    _os.environ.get("NASCAR_DATA_DIR") or _Path(__file__).resolve().parents[2] / "data"
)


def _active_season(default: int = _DEFAULT_SEASON) -> int:
    env = _os.environ.get("NASCAR_SEASON_YEAR", "").strip()
    if env.isdigit():
        return int(env)
    try:
        marker = _json.loads((_DATA_DIR / "active_season.json").read_text(encoding="utf-8"))
        return int(marker["season"])
    except Exception:
        return default


SEASON = _active_season()


def season_label(year: int) -> str:
    """NASCAR seasons are calendar-year seasons."""
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
        f"NASCAR season {SEASON} is active but data/announced_seasons/{SEASON}.json is "
        "missing or invalid — run `python -m nascar_predictions.bootstrap_next_season` first."
    )

# --------------------------------------------------------------------------- #
# Track-type classification — THE calibration/Elo stratum for a stock-car
# series. Superspeedways (pack racing, the Big One), intermediates (the 1.5-mile
# aero tracks), short tracks (contact racing) and road/street courses are close
# to four different sports; the model keeps a per-track-type Elo and the
# probability calibrator learns each stratum's variance separately.
#
# Classification is by track NAME (stable across seasons; track_ids drift) with
# a season condition for Atlanta (reprofiled into a drafting superspeedway for
# 2022). Road-course substrings are checked FIRST so e.g. "Daytona
# International Speedway Road Course" (2020-21) classifies as road, not
# superspeedway.
# --------------------------------------------------------------------------- #
TRACK_TYPES: tuple[str, ...] = ("superspeedway", "intermediate", "short", "road")

_ROAD_KEYS = (
    "road course",
    "street",
    "circuit of the americas",
    "sonoma",
    "watkins glen",
    "road america",
    "autodromo",
    "hermanos rodriguez",
    "mid-ohio",
)
_SUPERSPEEDWAY_KEYS = ("daytona", "talladega")
_SHORT_KEYS = (
    "bristol",
    "martinsville",
    "richmond",
    "phoenix",
    "iowa",
    "north wilkesboro",
    "new hampshire",
    "dover",
    "bowman gray",
)


def track_type_of(track_name: str, season: int) -> str:
    """Track type for a Cup venue: superspeedway / intermediate / short / road."""
    n = (track_name or "").lower()
    if any(k in n for k in _ROAD_KEYS):
        return "road"
    if any(k in n for k in _SUPERSPEEDWAY_KEYS):
        return "superspeedway"
    if "atlanta" in n:  # reprofiled into a drafting superspeedway for 2022
        return "superspeedway" if season >= 2022 else "intermediate"
    if any(k in n for k in _SHORT_KEYS):
        return "short"
    return "intermediate"


def driver_code(name: str) -> str:
    """Deterministic, season-stable driver code from a full name.

    First two letters of the first name + the full surname (suffixes dropped),
    ASCII-folded and uppercased: "Kyle Larson" → KYLARSON, "Kyle Busch" →
    KYBUSCH vs "Kurt Busch" → KUBUSCH. Stable across seasons (unlike car
    numbers) so the Elo replay tracks one identity per driver.
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
# Calendar — the 36 points races of the 2026 Cup season, taken from the
# official race list (cf.nascar.com cacher race_list_basic.json, race_type_id
# == 1 filters out the Clash / Duels / All-Star exhibitions) and verified live
# on 2026-07-07/08. Round number = date order of the points races. Races 1-26
# are the regular season; 27-36 are the Chase (see CUP_CHASE_FORMAT_2026).
# --------------------------------------------------------------------------- #
def _cal(rnd, key, track, race_name, date, race_id, track_type, kind, stages):
    return {
        "round": rnd,
        "key": key,
        "track": track,
        "raceName": race_name,
        "date": date,
        "raceId": race_id,
        "trackType": track_type,
        "kind": kind,
        "stageLaps": list(stages),
    }


_CALENDAR_2026: list[dict] = [
    _cal(1, "daytona-international-speedway", "Daytona International Speedway", "DAYTONA 500", "2026-02-15", 5596, "superspeedway", "oval", (65, 65, 70)),
    _cal(2, "atlanta-motor-speedway", "Atlanta Motor Speedway", "Autotrader 400", "2026-02-22", 5597, "superspeedway", "oval", (60, 100, 111)),
    _cal(3, "circuit-of-the-americas", "Circuit of The Americas", "DuraMAX Texas Grand Prix Powered by RelaDyne", "2026-03-01", 5598, "road", "circuit", (20, 25, 50)),
    _cal(4, "phoenix-raceway", "Phoenix Raceway", "Straight Talk Wireless 500", "2026-03-08", 5599, "short", "oval", (60, 125, 127)),
    _cal(5, "las-vegas-motor-speedway", "Las Vegas Motor Speedway", "Pennzoil 400 presented by Jiffy Lube", "2026-03-15", 5600, "intermediate", "oval", (80, 85, 102)),
    _cal(6, "darlington-raceway", "Darlington Raceway", "Goodyear 400", "2026-03-22", 5603, "intermediate", "oval", (90, 95, 108)),
    _cal(7, "martinsville-speedway", "Martinsville Speedway", "Cook Out 400", "2026-03-29", 5602, "short", "oval", (80, 100, 220)),
    _cal(8, "bristol-motor-speedway", "Bristol Motor Speedway", "Food City 500", "2026-04-12", 5604, "short", "oval", (125, 125, 255)),
    _cal(9, "kansas-speedway", "Kansas Speedway", "AdventHealth 400", "2026-04-19", 5607, "intermediate", "oval", (80, 85, 109)),
    _cal(10, "talladega-superspeedway", "Talladega Superspeedway", "Jack Link's 500", "2026-04-26", 5605, "superspeedway", "oval", (98, 45, 45)),
    _cal(11, "texas-motor-speedway", "Texas Motor Speedway", "Würth 400 presented by LIQUI MOLY", "2026-05-03", 5606, "intermediate", "oval", (80, 85, 102)),
    _cal(12, "watkins-glen-international", "Watkins Glen International", "Go Bowling at The Glen", "2026-05-10", 5621, "road", "circuit", (20, 30, 50)),
    _cal(13, "charlotte-motor-speedway", "Charlotte Motor Speedway", "Coca-Cola 600", "2026-05-24", 5610, "intermediate", "oval", (100, 100, 100)),
    _cal(14, "nashville-superspeedway", "Nashville Superspeedway", "Cracker Barrel 400", "2026-05-31", 5611, "intermediate", "oval", (90, 95, 115)),
    _cal(15, "michigan-international-speedway", "Michigan International Speedway", "FireKeepers Casino 400", "2026-06-07", 5612, "intermediate", "oval", (45, 75, 80)),
    _cal(16, "pocono-raceway", "Pocono Raceway", "Great American Getaway 400 presented by VISITPA", "2026-06-14", 5614, "intermediate", "oval", (30, 65, 65)),
    _cal(17, "san-diego-street-course", "San Diego Street Course", "Anduril 250", "2026-06-21", 5613, "road", "street", (20, 20, 35)),
    _cal(18, "sonoma-raceway", "Sonoma Raceway", "Toyota / Save Mart 350", "2026-06-28", 5617, "road", "circuit", (25, 30, 55)),
    _cal(19, "chicagoland-speedway", "Chicagoland Speedway", "eero 400", "2026-07-05", 5616, "intermediate", "oval", (80, 85, 102)),
    _cal(20, "atlanta-motor-speedway", "Atlanta Motor Speedway", "Quaker State 400 Available at Walmart", "2026-07-12", 5615, "superspeedway", "oval", (60, 100, 100)),
    _cal(21, "north-wilkesboro-speedway", "North Wilkesboro Speedway", "Window World 450", "2026-07-19", 5618, "short", "oval", (80, 185, 185)),
    _cal(22, "indianapolis-motor-speedway", "Indianapolis Motor Speedway", "Brickyard 400", "2026-07-26", 5619, "intermediate", "oval", (50, 50, 60)),
    _cal(23, "iowa-speedway", "Iowa Speedway", "Iowa Corn 350 Powered by Ethanol", "2026-08-09", 5620, "short", "oval", (70, 140, 140)),
    _cal(24, "richmond-raceway", "Richmond Raceway", "Cook Out 400", "2026-08-15", 5622, "short", "oval", (70, 160, 170)),
    _cal(25, "new-hampshire-motor-speedway", "New Hampshire Motor Speedway", "Dollar Tree 301", "2026-08-23", 5627, "short", "oval", (70, 115, 116)),
    _cal(26, "daytona-international-speedway", "Daytona International Speedway", "Coke Zero Sugar 400", "2026-08-29", 5623, "superspeedway", "oval", (35, 60, 65)),
    _cal(27, "darlington-raceway", "Darlington Raceway", "Cook Out Southern 500", "2026-09-06", 5624, "intermediate", "oval", (115, 115, 137)),
    _cal(28, "world-wide-technology-raceway", "World Wide Technology Raceway", "Enjoy Illinois 300", "2026-09-13", 5625, "intermediate", "oval", (45, 95, 100)),
    _cal(29, "bristol-motor-speedway", "Bristol Motor Speedway", "Bass Pro Shops Night Race", "2026-09-19", 5626, "short", "oval", (125, 125, 250)),
    _cal(30, "kansas-speedway", "Kansas Speedway", "Hollywood Casino 400", "2026-09-27", 5628, "intermediate", "oval", (80, 85, 102)),
    _cal(31, "las-vegas-motor-speedway", "Las Vegas Motor Speedway", "South Point 400", "2026-10-04", 5630, "intermediate", "oval", (80, 85, 102)),
    _cal(32, "charlotte-motor-speedway", "Charlotte Motor Speedway", "Bank of America 400", "2026-10-11", 5629, "intermediate", "oval", (25, 25, 217)),
    _cal(33, "phoenix-raceway", "Phoenix Raceway", "Freeway Insurance 500", "2026-10-18", 5633, "short", "oval", (60, 125, 127)),
    _cal(34, "talladega-superspeedway", "Talladega Superspeedway", "YellaWood 500", "2026-10-25", 5631, "superspeedway", "oval", (60, 60, 68)),
    _cal(35, "martinsville-speedway", "Martinsville Speedway", "Xfinity 500", "2026-11-01", 5632, "short", "oval", (130, 130, 240)),
    _cal(36, "homestead-miami-speedway", "Homestead-Miami Speedway", "NASCAR Championship Race", "2026-11-08", 5601, "intermediate", "oval", (80, 85, 102)),
]

_CAL_ACTIVE: list[dict] = (
    [
        _cal(
            int(e.get("round", i)),
            e["key"],
            e.get("track", e.get("name", e["key"])),
            e.get("raceName", e.get("name", "")),
            e.get("date", ""),
            e.get("raceId"),
            e.get("trackType", "intermediate"),
            e.get("kind", "oval"),
            tuple(e.get("stageLaps", (0, 0, 0))),
        )
        for i, e in enumerate(_ANNOUNCED["calendar"], start=1)
    ]
    if _ANNOUNCED
    else _CALENDAR_2026
)

CALENDAR: list[Venue] = [
    Venue(key=e["key"], name=e["track"], country="United States", kind=e["kind"])
    for e in _CAL_ACTIVE
]

#: round -> the full calendar metadata dict (track, raceName, date, raceId,
#: trackType, stageLaps). The freshness gate, the wrong-event guard and the
#: export all read this one table.
CALENDAR_META: dict[int, dict] = {e["round"]: e for e in _CAL_ACTIVE}


# How many rounds are "in the books". Derived from the committed real-data
# snapshot (data/official_<SEASON>.json) so one `python -m
# nascar_predictions.refresh` advances the whole pipeline; falls back to a
# literal if the snapshot is absent.
def _completed_from_snapshot(default: int) -> int:
    snap_path = _DATA_DIR / f"official_{SEASON}.json"
    try:
        snap = _json.loads(snap_path.read_text(encoding="utf-8"))
        if snap.get("season") == SEASON and "completedRounds" in snap:
            return int(snap["completedRounds"])
    except Exception:
        pass
    return default


COMPLETED_ROUNDS = _completed_from_snapshot(default=19 if SEASON == _DEFAULT_SEASON else 0)

# --------------------------------------------------------------------------- #
# Teams & manufacturers. NASCAR has two team-like groupings: the racing team
# (Hendrick, Gibbs, Penske — the Elo/rookie-pooling unit) and the manufacturer
# (Chevrolet / Ford / Toyota — a broader effect the model carries separately).
# Colors are curated for the current organisations; historical teams fall back
# to a default at export time.
# --------------------------------------------------------------------------- #
TEAMS: list[Team] = [
    Team(name="Hendrick Motorsports", color="#D6001C"),
    Team(name="Joe Gibbs Racing", color="#0A6B3B"),
    Team(name="Team Penske", color="#FFD100"),
    Team(name="23XI Racing", color="#5B2D8E"),
    Team(name="Trackhouse Racing", color="#E4002B"),
    Team(name="RFK Racing", color="#1B4499"),
    Team(name="Richard Childress Racing", color="#F5B300"),
    Team(name="Spire Motorsports", color="#00B2A9"),
    Team(name="Front Row Motorsports", color="#B7312C"),
    Team(name="Legacy Motor Club", color="#8A8D8F"),
    Team(name="Kaulig Racing", color="#00843D"),
    Team(name="Wood Brothers Racing", color="#C8102E"),
    Team(name="Haas Factory Team", color="#4B4F54"),
    Team(name="HYAK Motorsports", color="#0072CE"),
    Team(name="Rick Ware Racing", color="#6C6F70"),
]

MANUFACTURERS: tuple[str, ...] = ("Chevrolet", "Ford", "Toyota")
MANUFACTURER_COLORS: dict[str, str] = {
    "Chevrolet": "#C6A96E",
    "Ford": "#003478",
    "Toyota": "#EB0A1E",
}

# --------------------------------------------------------------------------- #
# Driver roster — the 38 drivers who started 7+ of the 19 completed 2026
# points races (full-timers + regular part-timers), teams/makes as raced at
# the most recent completed round. Derived from the official weekend feeds on
# 2026-07-08. One-off entries live in PART_TIME_DRIVERS so team/make lookups
# never miss.
# (code, name, team, make, latent_pace) — lower latent_pace = faster; pace is
# used ONLY by the synthetic fallback generator, never the predictor.
# --------------------------------------------------------------------------- #
_ROSTER: list[tuple[str, str, str, str, float]] = [
    ("KYLARSON", "Kyle Larson", "Hendrick Motorsports", "Chevrolet", 89.80),
    ("CHBELL", "Christopher Bell", "Joe Gibbs Racing", "Toyota", 89.86),
    ("WIBYRON", "William Byron", "Hendrick Motorsports", "Chevrolet", 89.90),
    ("DEHAMLIN", "Denny Hamlin", "Joe Gibbs Racing", "Toyota", 89.94),
    ("RYBLANEY", "Ryan Blaney", "Team Penske", "Ford", 89.98),
    ("TYREDDICK", "Tyler Reddick", "23XI Racing", "Toyota", 90.02),
    ("CHELLIOTT", "Chase Elliott", "Hendrick Motorsports", "Chevrolet", 90.06),
    ("CHBRISCOE", "Chase Briscoe", "Joe Gibbs Racing", "Toyota", 90.10),
    ("JOLOGANO", "Joey Logano", "Team Penske", "Ford", 90.14),
    ("TYGIBBS", "Ty Gibbs", "Joe Gibbs Racing", "Toyota", 90.18),
    ("ROCHASTAIN", "Ross Chastain", "Trackhouse Racing", "Chevrolet", 90.22),
    ("AUCINDRIC", "Austin Cindric", "Team Penske", "Ford", 90.26),
    ("BUWALLACE", "Bubba Wallace", "23XI Racing", "Toyota", 90.30),
    ("CHBUESCHER", "Chris Buescher", "RFK Racing", "Ford", 90.34),
    ("ALBOWMAN", "Alex Bowman", "Hendrick Motorsports", "Chevrolet", 90.38),
    ("BRKESELOWSKI", "Brad Keselowski", "RFK Racing", "Ford", 90.42),
    ("KYBUSCH", "Kyle Busch", "Richard Childress Racing", "Chevrolet", 90.46),
    ("SHGISBERGEN", "Shane Van Gisbergen", "Trackhouse Racing", "Chevrolet", 90.50),
    ("CAHOCEVAR", "Carson Hocevar", "Spire Motorsports", "Chevrolet", 90.54),
    ("JOBERRY", "Josh Berry", "Wood Brothers Racing", "Ford", 90.58),
    ("RYPREECE", "Ryan Preece", "RFK Racing", "Ford", 90.62),
    ("AJALLMENDINGER", "AJ Allmendinger", "Kaulig Racing", "Chevrolet", 90.66),
    ("ERJONES", "Erik Jones", "Legacy Motor Club", "Toyota", 90.70),
    ("MIMCDOWELL", "Michael McDowell", "Spire Motorsports", "Chevrolet", 90.74),
    ("DASUAREZ", "Daniel Suárez", "Spire Motorsports", "Chevrolet", 90.78),
    ("RISTENHOUSE", "Ricky Stenhouse Jr", "HYAK Motorsports", "Chevrolet", 90.82),
    ("AUDILLON", "Austin Dillon", "Richard Childress Racing", "Chevrolet", 90.86),
    ("ZASMITH", "Zane Smith", "Front Row Motorsports", "Ford", 90.90),
    ("JONEMECHEK", "John H. Nemechek", "Legacy Motor Club", "Toyota", 90.94),
    ("TOGILLILAND", "Todd Gilliland", "Front Row Motorsports", "Ford", 90.98),
    ("NOGRAGSON", "Noah Gragson", "Front Row Motorsports", "Ford", 91.02),
    ("COCUSTER", "Cole Custer", "Haas Factory Team", "Chevrolet", 91.06),
    ("RIHERBST", "Riley Herbst", "23XI Racing", "Toyota", 91.10),
    ("TYDILLON", "Ty Dillon", "Kaulig Racing", "Chevrolet", 91.14),
    ("COZILISCH", "Connor Zilisch", "Trackhouse Racing", "Chevrolet", 91.16),
    ("AUHILL", "Austin Hill", "Richard Childress Racing", "Chevrolet", 91.18),
    ("COHEIM", "Corey Heim", "23XI Racing", "Toyota", 91.22),
    ("COWARE", "Cody Ware", "Rick Ware Racing", "Chevrolet", 91.26),
]

# An announced season carries its own (provisional) roster forward.
if _ANNOUNCED and _ANNOUNCED.get("roster"):
    _ROSTER = [
        (r["code"], r["name"], r["team"], r.get("make", ""), float(r.get("pace", 90.5)))
        for r in _ANNOUNCED["roster"]
    ]

DRIVERS: list[dict[str, str]] = [
    {"code": c, "name": n, "team": t, "make": m} for (c, n, t, m, _) in _ROSTER
]

# Entrants seen in 2026 but not on the regular roster (one-off starts), so
# team/make lookups and standings aggregation never miss a code. refresh.py
# warns when a scraped classification carries a code neither table knows.
PART_TIME_DRIVERS: dict[str, dict[str, str]] = {
    "JJYELEY": {"name": "JJ Yeley", "team": "NY Racing Team", "make": "Chevrolet"},
    "JUALLGAIER": {"name": "Justin Allgaier", "team": "Hendrick Motorsports", "make": "Chevrolet"},
    "JIJOHNSON": {"name": "Jimmie Johnson", "team": "Legacy Motor Club", "make": "Toyota"},
    "CHFINCHUM": {"name": "Chad Finchum", "team": "Garage 66", "make": "Ford"},
    "CAMEARS": {"name": "Casey Mears", "team": "Beard Motorsports", "make": "Chevrolet"},
    "ANALFREDO": {"name": "Anthony Alfredo", "team": "Hendrick Motorsports", "make": "Chevrolet"},
    "BJMCLEOD": {"name": "BJ McLeod", "team": "Live Fast Motorsports", "make": "Chevrolet"},
    "JELOVE": {"name": "Jesse Love", "team": "Richard Childress Racing", "make": "Chevrolet"},
    "TIHILL": {"name": "Timmy Hill", "team": "Garage 66", "make": "Ford"},
    "DADYE": {"name": "Daniel Dye", "team": "Live Fast Motorsports", "make": "Chevrolet"},
    "KALEGGE": {"name": "Katherine Legge", "team": "Live Fast Motorsports", "make": "Chevrolet"},
    "CHSMITH": {"name": "Chandler Smith", "team": "Front Row Motorsports", "make": "Ford"},
    "COLAJOIE": {"name": "Corey LaJoie", "team": "RFK Racing", "make": "Ford"},
    "JOGASE": {"name": "Joey Gase", "team": "NY Racing Team", "make": "Chevrolet"},
    "JOBILICKI": {"name": "Josh Bilicki", "team": "Garage 66", "make": "Ford"},
    "KEMAGNUSSEN": {"name": "Kevin Magnussen", "team": "Trackhouse Racing", "make": "Chevrolet"},
}

if _ANNOUNCED:
    PART_TIME_DRIVERS = {
        code: {"name": d.get("name", code), "team": d.get("team", ""), "make": d.get("make", "")}
        for code, d in (_ANNOUNCED.get("part_time_drivers") or {}).items()
    }

TEAM_OF: dict[str, str] = {c: t for (c, _, t, _, _) in _ROSTER} | {
    c: d["team"] for c, d in PART_TIME_DRIVERS.items()
}
DRIVER_NAME: dict[str, str] = {c: n for (c, n, _, _, _) in _ROSTER} | {
    c: d["name"] for c, d in PART_TIME_DRIVERS.items()
}
MAKE_OF: dict[str, str] = {c: m for (c, _, _, m, _) in _ROSTER} | {
    c: d.get("make", "") for c, d in PART_TIME_DRIVERS.items()
}

# Latent pace — used ONLY by the synthetic results generator, never the predictor.
_TRUTH_PACE: dict[str, float] = {c: p for (c, _, _, _, p) in _ROSTER}

#: Points table alias for the active season (standings recompute fallback).
POINTS = RACE_POINTS_2026

# --------------------------------------------------------------------------- #
# Regulation eras — the NASCAR analog of motorsport_core.era.ERAS (which ships
# F1's table; core does not accept a custom table yet, so the boundary seasons
# live here and model.py applies the same hard-cut semantics).
# --------------------------------------------------------------------------- #
NASCAR_ERAS: tuple[tuple[str, int, int | None], ...] = (
    ("gen6", 2013, 2021),      # Gen-6 car (stage racing arrives 2017)
    ("nextgen", 2022, None),   # NextGen car
)

# ML training window: the NextGen era onward. Earlier seasons feed the Elo /
# era priors only, never the learned regressors.
ML_FIRST_SEASON = 2022
# Elo seed window: prior seasons replayed into the rating stack before the
# active season's rounds. 2019 keeps the window inside the stage/playoff era
# with one era boundary (2022) handled by the Elo inter-season shrink.
ELO_FIRST_SEASON = 2019
# Committed per-season snapshots go back to the cacher's archive floor.
# 2017 was the target (start of the stage/playoff era) but the live feed's
# history starts at 2018 — /2017/race_list_basic.json serves the 2018 season
# (verified 2026-07-08; every race's race_season says 2018), and the source's
# wrong-season guard refuses to ingest it twice. So: 2018.
HISTORY_FIRST_SEASON = 2018

# --------------------------------------------------------------------------- #
# NASCAR model parameters — the tuning knobs of the Cup model (see model.py).
#
# The Cup field is a spec-ish car (NextGen) with three manufacturers and
# multi-car teams: driver skill dominates, the team effect is real (equipment/
# pit crew/alliances) and the manufacturer adds a smaller shared effect.
# Track-type form is first-class: a superspeedway ace and a road-course ringer
# are different specialists, so a per-track-type Elo rides next to the overall
# rating.
# --------------------------------------------------------------------------- #

# Pace scale (a seconds-like proxy the Plackett-Luce sampler reads; lower = faster).
PACE_BASE = 90.0
PACE_SPREAD = 0.50

# Blend weights for the latent skill (relative; need not sum to 1).
SKILL_WEIGHTS = {
    "elo": 0.45,        # overall driver Elo (all track types)
    "track_elo": 0.35,  # per-track-type driver Elo for this round's track type
    "history": 0.35,    # smoothed current-season finishing history
    "team": 0.15,       # racing-team Elo (equipment / pit crew)
    "make": 0.10,       # manufacturer Elo (Chevrolet / Ford / Toyota)
    "ml": 0.50,         # optional gradient-boosted signal (ml_skill.py)
}

# Post-quali: when the REAL starting grid is known, the forecast conditions on
# it with a per-slot pace cost. The Cup grid is unusually informative (the
# metric-based lineup formula bakes in owner points + recent finish, and track
# position feeds stage points), so the weight is meaningful — tuned on the
# 2026 walk-forward post-quali replay (0.03 → MAE 9.14; 0.15 → 8.91, beating
# the grid-order baseline's 9.03; 0.25 flat). Unused pre-quali.
GRID_WEIGHT = 0.15

# A driver with fewer than this many prior Cup starts (across the Elo window)
# is treated as a rookie (pooled toward the team mean by the Elo prior).
ROOKIE_RACE_THRESHOLD = 5

# Monte Carlo sample count for the per-round probability + championship layers.
DEFAULT_SAMPLES = 4000

# Plackett-Luce temperature for CHAMPIONSHIP-horizon simulation. A single-race
# forecast uses the core default (0.5); a 10-27 race aggregate with a fixed
# point-estimate strength vector concentrates unrealistically (the model's own
# skill-estimation uncertainty compounds over the horizon), so the playoff /
# title Monte Carlo runs flatter. Tuned against the 2018-2024 elimination-era
# playoff backtest (champion mean-percentile and probability-vs-uniform gate).
CHAMPIONSHIP_TEMPERATURE = 1.0

# Skill-estimate uncertainty for the championship horizon: the title Monte
# Carlo averages over jittered strength vectors (pace_i + N(0, sigma), fresh
# draw per batch) so "who is actually fastest" is itself uncertain across
# simulations — the dominant source of long-horizon spread that per-race
# sampling noise cannot produce. sigma is in pace seconds (PACE_SPREAD = 0.5
# per skill z-unit, so 0.20 ≈ 0.4 z of rating uncertainty). Tuned on the
# playoff backtest alongside CHAMPIONSHIP_TEMPERATURE.
SKILL_UNCERTAINTY_SIGMA = 0.20
SKILL_UNCERTAINTY_BATCHES = 8

# Opt-in gradient-boosted skill regressor (nascar_predictions.ml_skill). ON by
# default but conservatively weighted; degrades silently to the Elo+history
# blend when deps/data are missing.
USE_ML_SKILL = True
ML_MIN_PRIOR_ROUNDS = 3
ML_MIN_TRAIN_ROWS = 12
ML_MIN_SPLIT_ROWS = 24

# --------------------------------------------------------------------------- #
# DNF / crash head — a first-class component of the Cup model. Attrition is a
# huge part of stock-car outcomes (superspeedway pack wrecks especially), so
# the race forecast COMPOSES it: sample DNFs first (per-driver Bernoulli
# hazard), rank the survivors by pace, send retirees to the back — the
# composition pattern from the F1 candidate model, promoted to the production
# path here because NASCAR classifies every car and attrition is 3-4x F1's.
# --------------------------------------------------------------------------- #
DNF_BASE_RATE_PRIOR = 0.10   # long-run Cup attrition prior (per start)
DNF_PRIOR_STRENGTH = 60.0    # starts of pseudo-evidence behind the base prior
DNF_K_DRIVER = 12.0          # shrinkage strength for per-driver hazard
DNF_TRACK_BLEND = 0.55       # weight on track-type attrition vs season base
DNF_DRIVER_BLEND = 0.45      # weight on the driver hazard in the final mix
DNF_CLIP = (0.02, 0.40)      # per-driver hazard bounds

# --------------------------------------------------------------------------- #
# Real data feed + calibration.
# --------------------------------------------------------------------------- #
MIN_REAL_ROUNDS_FOR_CALIBRATION = 6

# --------------------------------------------------------------------------- #
# Official NASCAR feeds (see sources/nascar_feed_source.py). No auth; be a
# polite guest: honest UA, ~1 request/second, disk-cached raw responses.
# Verified live 2026-07-07/08:
#   {CACHER}/{year}/race_list_basic.json           — season race list (all series)
#   {CACHER}/{year}/{series}/{race_id}/weekend-feed.json — results + stages + runs
# Some paths 403 (standings variants) — standings are derived from results.
# --------------------------------------------------------------------------- #
CACHER_BASE_URL = "https://cf.nascar.com/cacher"
CUP_SERIES_ID = 1
NASCAR_USER_AGENT = "motorsportverse/1.0"
