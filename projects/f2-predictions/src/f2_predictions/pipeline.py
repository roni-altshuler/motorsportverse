"""F2 prediction pipeline — orchestration over the F2 model and shared core.

This is where F2 reuses the shared core:

- **standings** → ``motorsport_core.standings`` (compute + merge sprint/feature)
- **skill + per-round forecast** → :mod:`f2_predictions.model` (the unique F2
  model: leakage-safe skill blend → reverse-grid sprint + merit feature heads)
- **championship Monte Carlo** → :func:`model.project_championship_f2`, which
  reuses the core Plackett-Luce sampler but alternates the sprint/feature tables.

The only F2-domain logic lives in :mod:`config` (points tables, calendar, roster)
and :mod:`model` (the modelling). This module just wires them to standings and
the export contract; everything numerically heavy is core.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import championship, standings

from . import config, model
from .datasource import F2DataSource


# --------------------------------------------------------------------------- #
# Standings (reuses core.standings)
# --------------------------------------------------------------------------- #
def _completed_races(source: F2DataSource, year: int) -> tuple[list[dict], list[dict]]:
    """Return (sprint_results, feature_results) over all completed rounds."""
    sprints, features = [], []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        races = source.race_results_for_round(year, rnd)
        sprints.append({r.competitor: r.position for r in races["sprint"]})
        features.append({r.competitor: r.position for r in races["feature"]})
    return sprints, features


def driver_standings(source: F2DataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    sprints, features = _completed_races(source, year)
    sprint_tbl = standings.compute_driver_standings(sprints, config.SPRINT_POINTS)
    feature_tbl = standings.compute_driver_standings(features, config.FEATURE_POINTS)
    return standings.merge_standings(sprint_tbl, feature_tbl)


def team_standings(source: F2DataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    sprints, features = _completed_races(source, year)
    sprint_tbl = standings.compute_team_standings(sprints, config.SPRINT_POINTS, config.TEAM_OF)
    feature_tbl = standings.compute_team_standings(features, config.FEATURE_POINTS, config.TEAM_OF)
    return standings.merge_standings(sprint_tbl, feature_tbl)


# --------------------------------------------------------------------------- #
# Skill + per-round forecast (delegated to the F2 model)
# --------------------------------------------------------------------------- #
def estimate_pace(source: F2DataSource, year: int, current_round: int) -> dict[str, float]:
    """Per-driver pace (lower = faster) from rounds STRICTLY BEFORE ``current_round``.

    Thin wrapper over :func:`model.estimate_skill` — kept as the project's stable
    "what's each driver's pace" entry point. Leakage-safe (the model asserts
    prior-only at its boundary).
    """
    return model.estimate_skill(source, year, current_round)


def forecast_round(
    source: F2DataSource, year: int, round: int, *, n_samples: int | None = None
) -> model.RoundForecastF2:
    """Full sprint + feature forecast for one round (the rich model output)."""
    return model.forecast_round(source, year, round, n_samples=n_samples)


@dataclass
class RoundPrediction:
    """Compact feature-race view of a round forecast (back-compat surface)."""

    season: int
    round: int
    venue_key: str
    venue_name: str
    qualifying_order: list[str]
    race_order: list[str]
    p_win: dict[str, float]
    p_podium: dict[str, float]


def predict_round(
    source: F2DataSource, year: int, round: int, *, n_samples: int | None = None
) -> RoundPrediction:
    """Qualifying + feature-race forecast for one round.

    Projects the rich :class:`model.RoundForecastF2` onto the compact shape the
    ``Predictor`` adapter and the season-summary export consume: qualifying order
    is the merit grid, the race view is the feature head.
    """
    fc = model.forecast_round(source, year, round, n_samples=n_samples)
    feature = fc.feature
    return RoundPrediction(
        season=year,
        round=round,
        venue_key=fc.venue_key,
        venue_name=fc.venue_name,
        qualifying_order=feature.grid,
        race_order=feature.order,
        p_win=feature.markets.p_win,
        p_podium=feature.markets.p_podium,
    )


# --------------------------------------------------------------------------- #
# Championship Monte Carlo (F2-aware: alternates sprint + feature points)
# --------------------------------------------------------------------------- #
def project_title(
    source: F2DataSource, year: int = config.SEASON, *, n_samples: int | None = None
) -> list[championship.TitleProjection]:
    """Project the drivers' championship over the remaining rounds."""
    table = driver_standings(source, year)
    current_points = {row.key: row.points for row in table}
    # Strength = skill estimated from everything raced so far.
    skill = model.estimate_skill(source, year, current_round=config.COMPLETED_ROUNDS + 1)
    remaining = len(config.CALENDAR) - config.COMPLETED_ROUNDS
    return model.project_championship_f2(
        current_points, skill, remaining_rounds=remaining, n_samples=n_samples
    )
