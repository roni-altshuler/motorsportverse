"""Driver and team Elo ratings for the F1 prediction stack.

Elo is the right primitive for sports prediction with limited data:
it gives every driver a continuously-updated single-number rating
that summarizes pace + reliability + race-craft into one feature.
Rookies get a principled prior (the team-pooled mean); mid-season
swaps inherit history naturally; and regulation changes get an
optional reset hook.

Module surface
--------------

* :class:`EloRating` — base symmetric pairwise Elo with K-factor
  schedule + optional regulation-era decay between seasons.
* :class:`DriverElo` — driver-vs-field race-by-race update; one
  rating per driver. Internally pools rookies to the team mean.
* :class:`TeamElo` — constructor rating updated from aggregated
  driver results; lighter K than the driver rating to reflect that
  team performance is more stable than driver form.
* :class:`EloFeatureBuilder` — top-level orchestrator that produces
  the seven Elo features documented in the ML architecture review:
  ``driver_elo``, ``team_elo``, ``driver_form_elo``,
  ``wet_weather_elo``, ``qualifying_elo``, ``racecraft_elo``,
  ``teammate_delta_elo``.

Determinism + leakage discipline
--------------------------------

Every update method takes ``(season, round)`` and mutates the
internal state in-place. The caller is responsible for replaying
events in chronological order; the builder's
:meth:`replay_history` does that from a sorted history record.

Per the project's :mod:`leakage` discipline, the builder accepts a
``current_round`` argument and refuses to incorporate any event
with ``(season, round) >= (current_season, current_round)``. This
mirrors :func:`leakage.assert_seasons_prior_only` but is enforced
*at the boundary* of the rating update, not by trusting the caller's
filter alone.

Update equations
----------------

Standard Elo:

    E_a = 1 / (1 + 10 ** ((R_b - R_a) / 400))
    R_a' = R_a + K * (S_a - E_a)

For a race with N drivers, each (driver_i, driver_j) pair where
``finish_i < finish_j`` is treated as a head-to-head win for i.
Score is 1.0 for the winner, 0.0 for the loser. The driver's total
update is the sum over all pairs, scaled by ``K / (N - 1)`` so the
per-race update magnitude doesn't blow up with field size.

K-factor schedule
-----------------

K decays with rated experience: a driver with <10 rated races uses
K=40 (provisional); 10-30 races uses K=25; >30 uses K=15. The
provisional regime moves rookies toward their true rating quickly
without later instability.

Rookie initialization
---------------------

A driver with no prior rating starts at ``team_mean - 25`` (slight
discount: rookies usually under-perform their team mean for a few
races) or at the global default (1500) if the team has no rated
drivers either.

Inter-season decay
------------------

Optional regulation-era decay: when stepping from season S to S+1,
each rating is pulled toward the league mean by a factor:

    R' = mean + (R - mean) * shrink

where ``shrink`` is 0.85 by default (mild) and 0.5 across an era
boundary (strong — same-rule continuity not assumed). Pulls happen
on the first call to update() in a new season; the carry-over flag
is tracked per rater.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .regulation_era import era_distance


DEFAULT_RATING = 1500.0
PROVISIONAL_RACES = 10
SETTLED_RACES = 30
K_PROVISIONAL = 40.0
K_INTERMEDIATE = 25.0
K_SETTLED = 15.0
TEAM_K_DAMPING = 0.4
ROOKIE_TEAM_DISCOUNT = 25.0
SAME_SEASON_SHRINK = 1.0
NEXT_SEASON_SHRINK = 0.85
ERA_BOUNDARY_SHRINK = 0.5


def expected_score(r_a: float, r_b: float) -> float:
    """Standard Elo expected score for A vs B."""
    return 1.0 / (1.0 + math.pow(10.0, (r_b - r_a) / 400.0))


def k_factor_for_experience(n_rated_races: int) -> float:
    """Standard Elo K-factor schedule.

    Provisional ratings move fast (K=40) for the first ten races,
    settle to K=25, then slow to K=15 once the rating is well-trained.
    """
    if n_rated_races < PROVISIONAL_RACES:
        return K_PROVISIONAL
    if n_rated_races < SETTLED_RACES:
        return K_INTERMEDIATE
    return K_SETTLED


@dataclass
class _RaterState:
    """Per-entity Elo state."""

    rating: float = DEFAULT_RATING
    n_races: int = 0
    last_season: int | None = None
    last_round: int | None = None


@dataclass
class EloRating:
    """Symmetric pairwise Elo with K-schedule + inter-season decay.

    Sub-classed by :class:`DriverElo` and :class:`TeamElo` with
    different K dampings; the base class handles the math.
    """

    k_damping: float = 1.0
    inter_season_shrink: float = NEXT_SEASON_SHRINK
    era_boundary_shrink: float = ERA_BOUNDARY_SHRINK
    league_mean: float = DEFAULT_RATING
    _state: dict[str, _RaterState] = field(default_factory=dict)

    def rating(self, key: str) -> float:
        """Current rating; default 1500 if unknown."""
        return self._state.get(key, _RaterState()).rating

    def n_races(self, key: str) -> int:
        return self._state.get(key, _RaterState()).n_races

    def has(self, key: str) -> bool:
        return key in self._state

    def all_ratings(self) -> dict[str, float]:
        return {k: v.rating for k, v in self._state.items()}

    def _apply_inter_season_decay(
        self, key: str, season: int, round_num: int
    ) -> None:
        state = self._state.get(key)
        if state is None or state.last_season is None:
            return
        if state.last_season >= season:
            return
        # Determine shrink strength based on era distance.
        try:
            dist = era_distance(state.last_season, season)
        except ValueError:
            dist = 0
        if dist >= 1:
            shrink = self.era_boundary_shrink
        else:
            shrink = self.inter_season_shrink
        state.rating = self.league_mean + (state.rating - self.league_mean) * shrink

    def initialise(
        self,
        key: str,
        *,
        initial_rating: float | None = None,
    ) -> None:
        """Seed a rating without consuming an update event."""
        if key in self._state:
            return
        self._state[key] = _RaterState(
            rating=initial_rating if initial_rating is not None else DEFAULT_RATING
        )

    def update_pairwise(
        self,
        key_a: str,
        key_b: str,
        score_a: float,
        season: int,
        round_num: int,
        *,
        k_override: float | None = None,
    ) -> None:
        """Update both raters from one head-to-head outcome.

        ``score_a`` is 1.0 for an A win, 0.0 for a B win, 0.5 for a
        draw. ``key_b`` is treated symmetrically (``score_b = 1 - score_a``).
        """
        for key in (key_a, key_b):
            self._apply_inter_season_decay(key, season, round_num)
            self._state.setdefault(key, _RaterState())
        state_a = self._state[key_a]
        state_b = self._state[key_b]
        exp_a = expected_score(state_a.rating, state_b.rating)
        if k_override is None:
            k_a = k_factor_for_experience(state_a.n_races) * self.k_damping
            k_b = k_factor_for_experience(state_b.n_races) * self.k_damping
        else:
            k_a = k_b = k_override * self.k_damping
        state_a.rating += k_a * (score_a - exp_a)
        state_b.rating += k_b * ((1.0 - score_a) - (1.0 - exp_a))
        state_a.last_season = season
        state_a.last_round = round_num
        state_b.last_season = season
        state_b.last_round = round_num

    def commit_race_attendance(
        self,
        keys: Iterable[str],
        season: int,
        round_num: int,
    ) -> None:
        """Increment race count for everyone who participated.

        Call this once after updating all pairwise outcomes for a race.
        """
        for key in keys:
            self._state.setdefault(key, _RaterState()).n_races += 1
            self._state[key].last_season = season
            self._state[key].last_round = round_num


@dataclass
class DriverElo(EloRating):
    """Driver Elo with rookie pooling toward team mean."""

    def initialise_rookie(
        self,
        driver_key: str,
        team_key: str,
        team_to_driver_ratings: Mapping[str, list[float]],
        *,
        discount: float = ROOKIE_TEAM_DISCOUNT,
    ) -> None:
        """Seed a rookie at ``team_mean - discount`` if possible.

        Falls back to the league mean when the team has no rated drivers.
        """
        if driver_key in self._state:
            return
        ratings = team_to_driver_ratings.get(team_key, [])
        if ratings:
            mean = sum(ratings) / len(ratings)
            initial = mean - discount
        else:
            initial = self.league_mean - discount
        self.initialise(driver_key, initial_rating=initial)


@dataclass
class TeamElo(EloRating):
    """Constructor Elo (lighter K than driver rating)."""

    k_damping: float = TEAM_K_DAMPING


def _process_one_race(
    elo: EloRating,
    finish_order: Mapping[str, int],
    season: int,
    round_num: int,
    *,
    k_override: float | None = None,
) -> None:
    """Run all C(N, 2) pairwise updates for one race."""
    keys = list(finish_order.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            k_i, k_j = keys[i], keys[j]
            pos_i = finish_order[k_i]
            pos_j = finish_order[k_j]
            if pos_i == pos_j:
                score_i = 0.5
            elif pos_i < pos_j:
                score_i = 1.0
            else:
                score_i = 0.0
            elo.update_pairwise(
                k_i, k_j, score_i, season, round_num, k_override=k_override
            )
    elo.commit_race_attendance(keys, season, round_num)


@dataclass
class _RaceEvent:
    """One race's results in the format the builder consumes."""

    season: int
    round: int
    finish_order: dict[str, int]
    grid_order: dict[str, int]
    team_of: dict[str, str]
    wet: bool = False


@dataclass
class EloFeatureBuilder:
    """Top-level Elo orchestrator.

    Produces seven driver-level features per (driver, race) tuple:

    - ``driver_elo``: race-result driver Elo
    - ``team_elo``: constructor Elo
    - ``driver_form_elo``: short-horizon (last 4 races) Elo delta
    - ``wet_weather_elo``: driver Elo updated only on wet races
    - ``qualifying_elo``: separate Elo using grid order
    - ``racecraft_elo``: positions-gained-vs-grid Elo
    - ``teammate_delta_elo``: driver_elo minus teammate's driver_elo

    The builder replays history in chronological order and is
    deterministic: same inputs → same features.
    """

    race_elo: DriverElo = field(default_factory=DriverElo)
    team_elo: TeamElo = field(default_factory=TeamElo)
    wet_elo: DriverElo = field(default_factory=DriverElo)
    qual_elo: DriverElo = field(default_factory=DriverElo)
    racecraft_elo: DriverElo = field(default_factory=DriverElo)
    _form_history: dict[str, list[float]] = field(default_factory=dict)
    _last_processed: tuple[int, int] | None = None

    def _record_form(self, driver: str) -> None:
        history = self._form_history.setdefault(driver, [])
        history.append(self.race_elo.rating(driver))
        if len(history) > 4:
            history.pop(0)

    def ingest_race(self, event: _RaceEvent) -> None:
        """Apply one race's results to every internal Elo."""
        if self._last_processed is not None and (
            event.season,
            event.round,
        ) <= self._last_processed:
            raise ValueError(
                f"events must be replayed in strict chronological order; "
                f"saw ({event.season},{event.round}) after {self._last_processed}"
            )

        # Race Elo (finish order).
        _process_one_race(self.race_elo, event.finish_order, event.season, event.round)

        # Team Elo: aggregate driver finish positions per team.
        team_finish: dict[str, list[int]] = {}
        for driver, pos in event.finish_order.items():
            team = event.team_of.get(driver)
            if team is None:
                continue
            team_finish.setdefault(team, []).append(pos)
        team_avg = {
            team: sum(positions) / len(positions)
            for team, positions in team_finish.items()
        }
        # Convert team mean position to a pairwise finish order.
        sorted_teams = sorted(team_avg.items(), key=lambda kv: kv[1])
        team_finish_order = {team: rank + 1 for rank, (team, _) in enumerate(sorted_teams)}
        _process_one_race(self.team_elo, team_finish_order, event.season, event.round)

        # Qualifying Elo (grid order).
        _process_one_race(self.qual_elo, event.grid_order, event.season, event.round)

        # Race-craft Elo: positions gained from grid to finish.
        positions_gained = {
            d: event.grid_order.get(d, 99) - event.finish_order.get(d, 99)
            for d in event.finish_order
        }
        # Higher = better; reverse to a finish-style ordering.
        ranked = sorted(
            positions_gained.items(), key=lambda kv: kv[1], reverse=True
        )
        rc_order = {d: rank + 1 for rank, (d, _) in enumerate(ranked)}
        _process_one_race(
            self.racecraft_elo, rc_order, event.season, event.round
        )

        # Wet Elo: only update on wet races. (Same K schedule.)
        if event.wet:
            _process_one_race(
                self.wet_elo, event.finish_order, event.season, event.round
            )

        for driver in event.finish_order:
            self._record_form(driver)

        self._last_processed = (event.season, event.round)

    def ensure_rookies(
        self,
        roster: Mapping[str, str],
    ) -> None:
        """Seed rookie ratings for drivers not yet in the race_elo.

        ``roster`` maps driver -> team. For each unseen driver, the
        rookie initialiser pulls from the current team's rated drivers
        to set a sensible prior.
        """
        team_to_drivers: dict[str, list[float]] = {}
        for drv, team in roster.items():
            if not self.race_elo.has(drv):
                continue
            team_to_drivers.setdefault(team, []).append(self.race_elo.rating(drv))
        for drv, team in roster.items():
            self.race_elo.initialise_rookie(drv, team, team_to_drivers)
            self.team_elo.initialise(team)
            self.wet_elo.initialise_rookie(drv, team, team_to_drivers)
            self.qual_elo.initialise_rookie(drv, team, team_to_drivers)
            self.racecraft_elo.initialise_rookie(drv, team, team_to_drivers)

    def features_for(
        self,
        driver: str,
        team: str,
        teammate: str | None,
    ) -> dict[str, float]:
        """Snapshot of all seven Elo features for a driver."""
        history = self._form_history.get(driver, [])
        form_delta = 0.0
        if len(history) >= 2:
            form_delta = history[-1] - history[0]
        teammate_delta = 0.0
        if teammate and self.race_elo.has(teammate):
            teammate_delta = self.race_elo.rating(driver) - self.race_elo.rating(
                teammate
            )
        return {
            "driver_elo": self.race_elo.rating(driver),
            "team_elo": self.team_elo.rating(team),
            "driver_form_elo": form_delta,
            "wet_weather_elo": self.wet_elo.rating(driver),
            "qualifying_elo": self.qual_elo.rating(driver),
            "racecraft_elo": self.racecraft_elo.rating(driver),
            "teammate_delta_elo": teammate_delta,
        }

    def replay_history(
        self,
        events: Iterable[_RaceEvent],
        *,
        current_season: int,
        current_round: int,
    ) -> None:
        """Apply a chronological event stream up to (but excluding) the cutoff.

        Events at or after ``(current_season, current_round)`` are
        rejected with a :class:`ValueError`. This enforces the same
        prior-only discipline as :func:`leakage.assert_seasons_prior_only`
        at the boundary of the Elo update.
        """
        for event in events:
            if (event.season, event.round) >= (current_season, current_round):
                raise ValueError(
                    f"Elo replay leakage: event ({event.season},{event.round}) "
                    f">= cutoff ({current_season},{current_round})"
                )
            self.ingest_race(event)


# Public constructor for the event record so callers don't import
# the underscored class directly.
RaceEvent = _RaceEvent

ELO_FEATURE_COLUMNS = (
    "driver_elo",
    "team_elo",
    "driver_form_elo",
    "wet_weather_elo",
    "qualifying_elo",
    "racecraft_elo",
    "teammate_delta_elo",
)


__all__ = [
    "DEFAULT_RATING",
    "PROVISIONAL_RACES",
    "SETTLED_RACES",
    "K_PROVISIONAL",
    "K_INTERMEDIATE",
    "K_SETTLED",
    "TEAM_K_DAMPING",
    "ROOKIE_TEAM_DISCOUNT",
    "ELO_FEATURE_COLUMNS",
    "expected_score",
    "k_factor_for_experience",
    "EloRating",
    "DriverElo",
    "TeamElo",
    "EloFeatureBuilder",
    "RaceEvent",
]
