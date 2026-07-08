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
