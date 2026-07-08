"""FE prediction pipeline — orchestration over the FE model and shared core.

This is where FE reuses the shared core:

- **standings** → ``motorsport_core.standings`` for the recomputed fallback;
  the committed snapshot carries the **official** API standings (exact totals
  including pole/fastest-lap bonuses) and wins whenever the feed is real.
- **skill + per-round forecast** → :mod:`formula_e_predictions.model` (the FE
  model: era-windowed Elo seed + leakage-safe in-season blend → single race
  head with post-quali grid conditioning).
- **championship Monte Carlo** → :func:`model.project_championship_fe`, which
  reuses the core Plackett-Luce sampler and folds in the expected pole/FL
  bonus points per remaining round.

The only FE-domain logic lives in :mod:`config` (points, calendar, roster,
eras) and :mod:`model` (the modelling). This module wires them to standings
and the export contract; everything numerically heavy is core.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import championship, standings

from . import config, model
from .datasource import FEDataSource
from .sources.composite import CompositeFESource
from .sources.snapshot import load_snapshot


# --------------------------------------------------------------------------- #
# Standings (official snapshot when real; core recompute otherwise)
# --------------------------------------------------------------------------- #
def _completed_races(source: FEDataSource, year: int) -> list[dict[str, int]]:
    """{code: position} per completed round."""
    return [
        {r.competitor: r.position for r in source.results(year, rnd)}
        for rnd in source.completed_rounds(year)
    ]


def official_standings(source: FEDataSource, year: int = config.SEASON) -> dict | None:
    """The official snapshot, but only when the source is actually serving real
    data (so synthetic-only unit tests fall back to computed standings).

    Race classifications alone omit pole (+3) and fastest-lap (+1) bonuses, so
    recomputed totals drift from the official table. The committed snapshot
    carries the exact official totals + per-round progression from the API's
    standings endpoint — use them for the public standings and the
    championship's current points so headline numbers match the official feed.
    """
    snap = load_snapshot(year)
    if not snap or snap.get("season") != year:
        return None
    try:
        prov = source.provenance(year, 1)
    except Exception:
        prov = "unknown"
    return snap if CompositeFESource.is_real(prov) else None


def driver_standings(source: FEDataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    races = _completed_races(source, year)
    return standings.compute_driver_standings(races, config.POINTS)


def current_driver_points(source: FEDataSource, year: int = config.SEASON) -> dict[str, float]:
    """Authoritative current driver points: official totals if the feed is
    real, else recomputed from race results. Keeps the championship coherent
    with the displayed standings."""
    official = official_standings(source, year)
    if official:
        return {d["code"]: float(d["points"]) for d in official.get("driverStandings", [])}
    return {row.key: row.points for row in driver_standings(source, year)}


def team_standings(source: FEDataSource, year: int = config.SEASON) -> list[standings.StandingRow]:
    races = _completed_races(source, year)
    return standings.compute_team_standings(races, config.POINTS, source.team_of(year))


# --------------------------------------------------------------------------- #
# Skill + per-round forecast (delegated to the FE model)
# --------------------------------------------------------------------------- #
def estimate_pace(source: FEDataSource, year: int, current_round: int) -> dict[str, float]:
    """Per-driver pace (lower = faster) from rounds STRICTLY BEFORE
    ``current_round`` (plus the era-windowed prior-season Elo seed).

    Thin wrapper over :func:`model.estimate_skill` — the project's stable
    "what's each driver's pace" entry point. Leakage-safe (the model asserts
    prior-only at its boundary).
    """
    return model.estimate_skill(source, year, current_round)


def forecast_round(
    source: FEDataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
) -> model.RoundForecastFE:
    """Full race forecast for one round (the rich model output).

    ``known_grid`` (actual qualifying order) routes to the model's post-quali
    path.
    """
    return model.forecast_round(source, year, round, n_samples=n_samples, known_grid=known_grid)


@dataclass
class RoundPrediction:
    """Compact view of a round forecast (back-compat surface)."""

    season: int
    round: int
    venue_key: str
    venue_name: str
    qualifying_order: list[str]
    race_order: list[str]
    p_win: dict[str, float]
    p_podium: dict[str, float]


def predict_round(
    source: FEDataSource, year: int, round: int, *, n_samples: int | None = None
) -> RoundPrediction:
    """Qualifying + race forecast for one round.

    Projects the rich :class:`model.RoundForecastFE` onto the compact shape the
    ``Predictor`` adapter and the season-summary export consume: qualifying
    order is the merit grid, the race view is the (single) race head.
    """
    fc = model.forecast_round(source, year, round, n_samples=n_samples)
    race = fc.race
    return RoundPrediction(
        season=year,
        round=round,
        venue_key=fc.venue_key,
        venue_name=fc.venue_name,
        qualifying_order=race.grid,
        race_order=race.order,
        p_win=race.markets.p_win,
        p_podium=race.markets.p_podium,
    )


# --------------------------------------------------------------------------- #
# Championship Monte Carlo (FE-aware: expected pole/FL bonuses folded in)
# --------------------------------------------------------------------------- #
def project_title(
    source: FEDataSource, year: int = config.SEASON, *, n_samples: int | None = None
) -> list[championship.TitleProjection]:
    """Project the drivers' championship over the remaining rounds."""
    current_points = current_driver_points(source, year)
    completed = len(source.completed_rounds(year))
    # Strength = skill estimated from everything raced so far.
    skill = model.estimate_skill(source, year, current_round=completed + 1)
    remaining = source.total_rounds(year) - completed
    return model.project_championship_fe(
        current_points, skill, remaining_rounds=remaining, n_samples=n_samples
    )
