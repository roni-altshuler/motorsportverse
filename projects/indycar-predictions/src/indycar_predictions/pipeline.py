"""IndyCar prediction pipeline — orchestration over the model and shared core.

This is where IndyCar reuses the shared core:

- **standings** → the committed history file carries the **official** curated
  standings (points AS AWARDED, verified against Wikipedia's standings grid —
  see data/CURATION_REPORT.md); ``motorsport_core.standings`` provides the
  recomputed fallback (base race points only — an approximation, used for
  synthetic runs).
- **skill + per-round forecast** → :mod:`indycar_predictions.model` (dual
  oval/road-street Elo blend → DNF-composed race head).
- **championship** → straight cumulative points via
  :func:`model.project_championship_indycar` — IndyCar has NO playoffs, so the
  title odds are a plain remaining-rounds Monte Carlo over the base points
  table plus the expected pole/laps-led bonuses. No resets, no eliminations.

The only IndyCar-domain logic lives in :mod:`config` (points, calendar,
roster, track types) and :mod:`model`; everything numerically heavy is core.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import championship, standings

from . import config, model
from .datasource import IndycarDataSource
from .sources.composite import CompositeIndycarSource
from .sources.snapshot import load_snapshot


# --------------------------------------------------------------------------- #
# Standings (official curated totals when real; core recompute otherwise)
# --------------------------------------------------------------------------- #
def _completed_races(source: IndycarDataSource, year: int) -> list[dict[str, int]]:
    """{code: position} per completed round."""
    return [
        {r.competitor: r.position for r in source.results(year, rnd)}
        for rnd in source.completed_rounds(year)
    ]


def official_standings(source: IndycarDataSource, year: int = 0) -> list[dict] | None:
    """The curated official standings, but only when the source is actually
    serving real data (so synthetic-only unit tests fall back to computed
    standings).

    Race classifications alone would miss pole/laps-led bonuses if summed from
    the base table, but the curated files record points AS AWARDED — both the
    per-round rows and the final_standings grid come from the same verified
    source, so the official grid is authoritative for the public standings and
    the championship's current points.
    """
    year = year or config.SEASON
    snap = load_snapshot(year)
    if not snap or snap.get("season") != year:
        return None
    try:
        prov = source.provenance(year, 1)
    except Exception:
        prov = "unknown"
    if not CompositeIndycarSource.is_real(prov):
        return None
    rows = source.standings_rows(year)
    return rows or None


def driver_standings(source: IndycarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_driver_standings(races, config.POINTS)


def awarded_points_by_driver(source: IndycarDataSource, year: int = 0) -> dict[str, float]:
    """Per-driver sum of points AS AWARDED across completed rounds (exact for
    full-detail rounds; base-table fallback where a curated row lacks points).
    """
    year = year or config.SEASON
    totals: dict[str, float] = {}
    for rnd in source.completed_rounds(year):
        rows = source.race_rows(year, rnd)
        if rows:
            for r in rows:
                pts = r.get("points")
                if pts is None and r.get("position"):
                    pts = float(config.POINTS.get(int(r["position"]), 5))
                totals[r["code"]] = totals.get(r["code"], 0.0) + float(pts or 0.0)
        else:
            for res in source.results(year, rnd):
                pts = res.points
                if pts is None and res.position:
                    pts = float(config.POINTS.get(int(res.position), 5))
                totals[res.competitor] = totals.get(res.competitor, 0.0) + float(pts or 0.0)
    return totals


def current_driver_points(source: IndycarDataSource, year: int = 0) -> dict[str, float]:
    """Authoritative current driver points: the curated official grid if the
    source is real, else recomputed from race results."""
    year = year or config.SEASON
    official = official_standings(source, year)
    if official:
        return {d["code"]: float(d["points"]) for d in official}
    return {row.key: row.points for row in driver_standings(source, year)}


def team_standings(source: IndycarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_team_standings(races, config.POINTS, source.team_of(year))


def engine_standings(source: IndycarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_team_standings(races, config.POINTS, source.engine_of(year))


# --------------------------------------------------------------------------- #
# Skill + per-round forecast (delegated to the model)
# --------------------------------------------------------------------------- #
def estimate_pace(source: IndycarDataSource, year: int, current_round: int) -> dict[str, float]:
    """Per-driver pace (lower = faster) from rounds STRICTLY BEFORE
    ``current_round`` (plus the era-windowed prior-season Elo seed)."""
    return model.estimate_skill(source, year, current_round)


def forecast_round(
    source: IndycarDataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
) -> model.RoundForecastIndycar:
    """Full race forecast for one round (the rich model output).

    ``known_grid`` (actual qualifying order) routes to the model's post-quali
    path.
    """
    return model.forecast_round(source, year, round, n_samples=n_samples, known_grid=known_grid)


# --------------------------------------------------------------------------- #
# Championship (straight points — no playoffs)
# --------------------------------------------------------------------------- #
def project_title(
    source: IndycarDataSource, year: int = 0, *, n_samples: int | None = None
) -> list[championship.TitleProjection]:
    """Project the drivers' championship over the remaining rounds."""
    year = year or config.SEASON
    current_points = current_driver_points(source, year)
    completed = len(source.completed_rounds(year))
    # Strength = skill estimated from everything raced so far.
    skill = model.estimate_skill(source, year, current_round=completed + 1)
    # Every driver with points must be in the simulation, even if outside the
    # current entry picture (Indy-500-only entries) — back-of-field pace.
    worst = max(skill.values()) if skill else config.PACE_BASE
    for c in current_points:
        skill.setdefault(c, worst + 0.5)
    remaining = source.total_rounds(year) - completed
    return model.project_championship_indycar(
        current_points, skill, remaining_rounds=remaining, n_samples=n_samples
    )


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
    source: IndycarDataSource, year: int, round: int, *, n_samples: int | None = None
) -> RoundPrediction:
    """Qualifying + race forecast for one round (compact projection)."""
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
