"""Championship standings from race results — sport-agnostic.

Every motorsport championship is "accumulate points over rounds, rank
competitors and teams". The *points table* and *race format* vary by series, so
this module takes the points mapping as a parameter and treats each scored race
as one entry in a results list. Multi-race weekends (e.g. F2's sprint + feature)
are just two entries.

This is shared infrastructure: F2 uses it today; any RaceIQ series can.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

# Race result for one scored session: competitor code -> finishing position
# (1 = winner). Competitors who DNF/are absent are simply omitted (no points).
RaceResult = Mapping[str, int]


@dataclass
class StandingRow:
    """One competitor's (or team's) championship line."""

    key: str
    points: float = 0.0
    wins: int = 0
    podiums: int = 0
    rounds: int = 0
    best_finish: int | None = None
    positions: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "points": self.points,
            "wins": self.wins,
            "podiums": self.podiums,
            "rounds": self.rounds,
            "best_finish": self.best_finish,
        }


def points_for(position: int, points: Mapping[int, float]) -> float:
    """Points awarded for a finishing position (0 outside the points table)."""
    return float(points.get(position, 0.0))


def compute_driver_standings(
    results: Sequence[RaceResult],
    points: Mapping[int, float],
    *,
    bonus: Mapping[str, float] | None = None,
) -> list[StandingRow]:
    """Rank competitors by accumulated points across ``results``.

    Parameters
    ----------
    results
        One mapping per scored race (sprint, feature, …), competitor -> position.
    points
        Position -> points table for the series.
    bonus
        Optional competitor -> extra points (pole, fastest lap, etc.), already
        summed by the caller.

    Ties are broken by countback: more wins, then more podiums, then better best
    finish — the standard FIA convention.
    """
    rows: dict[str, StandingRow] = {}
    for race in results:
        for competitor, position in race.items():
            row = rows.setdefault(competitor, StandingRow(key=competitor))
            row.points += points_for(position, points)
            row.rounds += 1
            row.positions.append(position)
            if position == 1:
                row.wins += 1
            if position <= 3:
                row.podiums += 1
            row.best_finish = position if row.best_finish is None else min(row.best_finish, position)
    if bonus:
        for competitor, extra in bonus.items():
            rows.setdefault(competitor, StandingRow(key=competitor)).points += float(extra)
    return _sorted(rows.values())


def compute_team_standings(
    results: Sequence[RaceResult],
    points: Mapping[int, float],
    team_of: Mapping[str, str],
    *,
    bonus: Mapping[str, float] | None = None,
) -> list[StandingRow]:
    """Rank teams by the summed points of their competitors.

    ``team_of`` maps competitor code -> team name. Competitors with no team
    mapping are skipped (with a clear contract: every scorer should be mapped).
    """
    rows: dict[str, StandingRow] = {}
    for race in results:
        for competitor, position in race.items():
            team = team_of.get(competitor)
            if team is None:
                continue
            row = rows.setdefault(team, StandingRow(key=team))
            row.points += points_for(position, points)
            row.rounds += 1
            row.positions.append(position)
            if position == 1:
                row.wins += 1
            if position <= 3:
                row.podiums += 1
            row.best_finish = position if row.best_finish is None else min(row.best_finish, position)
    if bonus:
        for competitor, extra in bonus.items():
            team = team_of.get(competitor)
            if team is not None:
                rows.setdefault(team, StandingRow(key=team)).points += float(extra)
    return _sorted(rows.values())


def merge_standings(*tables: Sequence[StandingRow]) -> list[StandingRow]:
    """Combine standings computed under different points tables.

    Multi-race weekends use different points per session (F2 sprint + feature,
    F1/MotoGP sprint). Compute each session-type with its own table via
    :func:`compute_driver_standings`, then merge here — points, wins, podiums,
    rounds and best-finish all aggregate, and the result is re-ranked.
    """
    merged: dict[str, StandingRow] = {}
    for table in tables:
        for r in table:
            m = merged.setdefault(r.key, StandingRow(key=r.key))
            m.points += r.points
            m.wins += r.wins
            m.podiums += r.podiums
            m.rounds += r.rounds
            m.positions.extend(r.positions)
            if r.best_finish is not None:
                m.best_finish = (
                    r.best_finish if m.best_finish is None else min(m.best_finish, r.best_finish)
                )
    return _sorted(merged.values())


def _sorted(rows) -> list[StandingRow]:
    return sorted(
        rows,
        key=lambda r: (-r.points, -r.wins, -r.podiums, r.best_finish or 99),
    )


__all__ = [
    "RaceResult",
    "StandingRow",
    "points_for",
    "compute_driver_standings",
    "compute_team_standings",
    "merge_standings",
]
