"""F2 prediction pipeline — F2 glue over motorsport-core.

This is where F2 reuses the shared core:

- **standings** → ``motorsport_core.standings`` (compute + merge sprint/feature)
- **pace estimation** → leakage-safe rolling mean of prior finishes
  (``motorsport_core.leakage`` guards the boundary)
- **qualifying + race probabilities** → ``motorsport_core.calibration``
  (Plackett-Luce)
- **championship Monte Carlo** → ``motorsport_core.championship``

The only F2-domain logic here is the points tables, the two-race weekend shape,
and the pace-from-results estimator. Everything numerically heavy is core.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import calibration, championship, leakage, standings

from . import config
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
# Pace estimation (leakage-safe) — the predictor's only learned input
# --------------------------------------------------------------------------- #
def estimate_pace(source: F2DataSource, year: int, current_round: int) -> dict[str, float]:
    """Estimate per-driver pace from results in rounds STRICTLY BEFORE
    ``current_round``. Lower = faster, on the same scale the calibration sampler
    expects. Drivers with no history fall back to the field mean.

    Uses ``motorsport_core.leakage.assert_prior_only`` at the boundary so a bug
    that leaks the target round fails loudly.
    """
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    # Leakage guard: the map we aggregate must contain only prior rounds.
    leakage.assert_prior_only(
        {r: None for r in prior_rounds}, current_round=current_round, label="f2.estimate_pace"
    )

    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rnd in prior_rounds:
        races = source.race_results_for_round(year, rnd)
        for race in (races["sprint"], races["feature"]):
            for res in race:
                sums[res.competitor] = sums.get(res.competitor, 0.0) + res.position
                counts[res.competitor] = counts.get(res.competitor, 0) + 1

    codes = [d["code"] for d in config.DRIVERS]
    if not counts:  # no history yet — neutral pace for everyone
        return {c: 90.0 for c in codes}

    avg_pos = {c: sums[c] / counts[c] for c in sums}
    field_mean = sum(avg_pos.values()) / len(avg_pos)
    # Map average finishing position to a pace proxy (P1≈89.0s, each place +0.1s).
    return {c: 89.0 + 0.10 * avg_pos.get(c, field_mean) for c in codes}


# --------------------------------------------------------------------------- #
# Predictions (reuse core.calibration)
# --------------------------------------------------------------------------- #
@dataclass
class RoundPrediction:
    season: int
    round: int
    venue_key: str
    venue_name: str
    qualifying_order: list[str]
    race_order: list[str]
    p_win: dict[str, float]
    p_podium: dict[str, float]


def predict_round(
    source: F2DataSource, year: int, round: int, *, n_samples: int = 4000
) -> RoundPrediction:
    """Qualifying + race forecast for one round, from leakage-safe pace."""
    pace = estimate_pace(source, year, round)
    venue = source._venue(round)

    # Qualifying: deterministic order by estimated pace (fastest first).
    quali_order = sorted(pace, key=lambda c: pace[c])

    # Race: Plackett-Luce probabilities + expected finishing order (by mean rank).
    probs = calibration.plackett_luce_probabilities(pace, n_samples=n_samples)
    # Expected order: sort by descending win+podium signal, tie-break on pace.
    race_order = sorted(
        pace,
        key=lambda c: (-probs.p_podium.get(c, 0.0), -probs.p_win.get(c, 0.0), pace[c]),
    )
    return RoundPrediction(
        season=year,
        round=round,
        venue_key=venue.key,
        venue_name=venue.name,
        qualifying_order=quali_order,
        race_order=race_order,
        p_win=probs.p_win,
        p_podium=probs.p_podium,
    )


# --------------------------------------------------------------------------- #
# Championship Monte Carlo (reuse core.championship)
# --------------------------------------------------------------------------- #
def project_title(
    source: F2DataSource, year: int = config.SEASON, *, n_samples: int = 4000
) -> list[championship.TitleProjection]:
    """Project the drivers' championship over the remaining rounds."""
    table = driver_standings(source, year)
    current_points = {row.key: row.points for row in table}
    # Strength = pace estimated from everything raced so far.
    pace = estimate_pace(source, year, current_round=config.COMPLETED_ROUNDS + 1)
    remaining = len(config.CALENDAR) - config.COMPLETED_ROUNDS
    return championship.project_championship(
        current_points,
        pace,
        remaining_rounds=remaining,
        points=config.FEATURE_POINTS,
        races_per_round=2,  # sprint + feature
        n_samples=n_samples,
    )
