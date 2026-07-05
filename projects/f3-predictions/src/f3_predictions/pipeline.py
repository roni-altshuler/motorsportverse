"""F3 prediction pipeline — orchestration over the F3 model and shared core.

This is where F3 reuses the shared core:

- **standings** → ``motorsport_core.standings`` (compute + merge sprint/feature)
- **skill + per-round forecast** → :mod:`f3_predictions.model` (the unique F3
  model: leakage-safe skill blend → reverse-grid sprint + merit feature heads)
- **championship Monte Carlo** → :func:`model.project_championship_f3`, which
  reuses the core Plackett-Luce sampler but alternates the sprint/feature tables.

The only F3-domain logic lives in :mod:`config` (points tables, calendar, roster)
and :mod:`model` (the modelling). This module just wires them to standings and
the export contract; everything numerically heavy is core.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import championship, standings

from . import config, model
from .datasource import F3DataSource
from .sources.composite import CompositeF3Source
from .sources.snapshot import load_snapshot


# --------------------------------------------------------------------------- #
# Standings (reuses core.standings)
# --------------------------------------------------------------------------- #
def _completed_races(source: F3DataSource, year: int) -> tuple[list[dict], list[dict]]:
    """Return (sprint_results, feature_results) over all completed rounds."""
    sprints, features = [], []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        races = source.race_results_for_round(year, rnd)
        sprints.append({r.competitor: r.position for r in races["sprint"]})
        features.append({r.competitor: r.position for r in races["feature"]})
    return sprints, features


def official_standings(source: F3DataSource, year: int = config.SEASON) -> dict | None:
    """The official snapshot, but only when the source is actually serving real
    data (so synthetic-only unit tests fall back to computed standings).

    Race classifications alone omit pole (+2) and fastest-lap (+1) bonuses, so
    recomputed totals drift from the official table. The committed snapshot
    carries the exact official totals + per-round breakdown — use them for the
    public standings and the championship's current points so the headline
    numbers match fiaformula3.com exactly.
    """
    snap = load_snapshot()
    if not snap or snap.get("season") != year:
        return None
    try:
        prov = source.provenance(year, 1, race_index=1)
    except Exception:
        prov = "unknown"
    return snap if CompositeF3Source.is_real(prov) else None


def driver_standings(source: F3DataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    sprints, features = _completed_races(source, year)
    sprint_tbl = standings.compute_driver_standings(sprints, config.SPRINT_POINTS)
    feature_tbl = standings.compute_driver_standings(features, config.FEATURE_POINTS)
    return standings.merge_standings(sprint_tbl, feature_tbl)


def current_driver_points(source: F3DataSource, year: int = config.SEASON) -> dict[str, float]:
    """Authoritative current driver points: official totals if the feed is real,
    else recomputed from race results. Keeps the championship coherent with the
    displayed standings."""
    official = official_standings(source, year)
    if official:
        return {d["code"]: float(d["points"]) for d in official.get("driverStandings", [])}
    return {row.key: row.points for row in driver_standings(source, year)}


def team_standings(source: F3DataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    sprints, features = _completed_races(source, year)
    sprint_tbl = standings.compute_team_standings(sprints, config.SPRINT_POINTS, config.TEAM_OF)
    feature_tbl = standings.compute_team_standings(features, config.FEATURE_POINTS, config.TEAM_OF)
    return standings.merge_standings(sprint_tbl, feature_tbl)


# --------------------------------------------------------------------------- #
# Skill + per-round forecast (delegated to the F3 model)
# --------------------------------------------------------------------------- #
def estimate_pace(source: F3DataSource, year: int, current_round: int) -> dict[str, float]:
    """Per-driver pace (lower = faster) from rounds STRICTLY BEFORE ``current_round``.

    Thin wrapper over :func:`model.estimate_skill` — kept as the project's stable
    "what's each driver's pace" entry point. Leakage-safe (the model asserts
    prior-only at its boundary).
    """
    return model.estimate_skill(source, year, current_round)


def forecast_round(
    source: F3DataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
) -> model.RoundForecastF3:
    """Full sprint + feature forecast for one round (the rich model output).

    ``known_grid`` (actual qualifying order) routes to the model's post-quali path.
    """
    return model.forecast_round(source, year, round, n_samples=n_samples, known_grid=known_grid)


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
    source: F3DataSource, year: int, round: int, *, n_samples: int | None = None
) -> RoundPrediction:
    """Qualifying + feature-race forecast for one round.

    Projects the rich :class:`model.RoundForecastF3` onto the compact shape the
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
# Championship Monte Carlo (F3-aware: alternates sprint + feature points)
# --------------------------------------------------------------------------- #
def project_title(
    source: F3DataSource, year: int = config.SEASON, *, n_samples: int | None = None
) -> list[championship.TitleProjection]:
    """Project the drivers' championship over the remaining rounds."""
    current_points = current_driver_points(source, year)
    # Strength = skill estimated from everything raced so far.
    skill = model.estimate_skill(source, year, current_round=config.COMPLETED_ROUNDS + 1)
    remaining = len(config.CALENDAR) - config.COMPLETED_ROUNDS
    return model.project_championship_f3(
        current_points, skill, remaining_rounds=remaining, n_samples=n_samples
    )
