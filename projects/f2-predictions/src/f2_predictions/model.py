"""The unique F2 prediction model.

F2 is not F1 and it is not the thin pace-average predictor this project shipped
first. Two facts about the series drive the whole design:

1. **Spec series.** Every car is the same chassis/engine/tyre, so *driver skill
   dominates* and the constructor effect is small — the opposite weighting from
   F1, where the car explains most of the variance.
2. **Two structurally different races per weekend.** The **feature race** starts
   from a merit qualifying grid; the **sprint race** starts from the feature-quali
   **top-10 reversed**. A fast driver lining up P10 in the sprint has to overtake
   to win — that reverse grid is the single most F2-specific thing here and has no
   F1 analogue.

So the model estimates a leakage-safe *latent skill* per driver (blending Elo,
finishing history, and an optional Bayesian prior), then routes that skill through
two race-type heads:

* feature head — sample finishing orders directly from skill (merit grid);
* sprint head — add a grid-position penalty over the reversed grid, then sample,
  producing the characteristic high-variance sprint.

Everything numerically heavy is reused from ``motorsport-core``:
:func:`~motorsport_core.calibration.plackett_luce_probabilities` /
``sample_finishing_orders`` for the Monte Carlo, :class:`~motorsport_core.elo.EloFeatureBuilder`
for skill (with rookie pooling for the series' high driver turnover), and
:mod:`~motorsport_core.leakage` to keep every estimate prior-only. The reverse-grid
and race-type logic is the genuinely new, F2-specific code — and it stays in the
project, not in sport-agnostic core.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from motorsport_core import calibration, conformal, elo, leakage
from motorsport_core.calibration import MarketProbabilities
from motorsport_core.championship import TitleProjection

from . import config
from .datasource import F2DataSource

SPRINT = "sprint"
FEATURE = "feature"


# --------------------------------------------------------------------------- #
# Output containers
# --------------------------------------------------------------------------- #
@dataclass
class RaceForecast:
    """Forecast for one scored race (sprint or feature) within a round."""

    race_type: str                      # "sprint" | "feature"
    grid: list[str]                     # codes in starting-grid order
    order: list[str]                    # expected finishing order (codes)
    score: dict[str, float]             # per-driver pace/score, lower = faster
    markets: MarketProbabilities        # win/podium/top6/top10 + H2H
    mean_finish: dict[str, float]       # MC mean finishing position
    range_low: dict[str, int]           # MC 10th-percentile finish (optimistic)
    range_high: dict[str, int]          # MC 90th-percentile finish (pessimistic)
    confidence: dict[str, str]          # "High" | "Medium" | "Low" per driver
    n_samples: int
    temperature: float


@dataclass
class RoundForecastF2:
    """Both scored races for one round, plus venue metadata."""

    season: int
    round: int
    venue_key: str
    venue_name: str
    country: str | None
    sprint: RaceForecast
    feature: RaceForecast


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def _zscores(values: Mapping[str, float]) -> dict[str, float]:
    """Standardise a per-driver signal; all-equal input maps to all zeros."""
    keys = list(values.keys())
    arr = np.array([values[k] for k in keys], dtype=float)
    sd = float(arr.std())
    if sd <= 1e-9:
        return {k: 0.0 for k in keys}
    mu = float(arr.mean())
    return {k: (float(values[k]) - mu) / sd for k in keys}


def _teammate_of() -> dict[str, str | None]:
    """Map each driver to their (single) teammate, for the Elo teammate delta."""
    by_team: dict[str, list[str]] = {}
    for code, team in config.TEAM_OF.items():
        by_team.setdefault(team, []).append(code)
    out: dict[str, str | None] = {}
    for codes in by_team.values():
        for c in codes:
            others = [o for o in codes if o != c]
            out[c] = others[0] if others else None
    return out


def _prior_history(
    source: F2DataSource, year: int, prior_rounds: list[int]
) -> tuple[dict[str, float], dict[str, int]]:
    """Mean finishing position and race count per driver over prior rounds.

    Pools the sprint and feature classifications of every completed prior round.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rnd in prior_rounds:
        races = source.race_results_for_round(year, rnd)
        for race in (races[SPRINT], races[FEATURE]):
            for res in race:
                sums[res.competitor] = sums.get(res.competitor, 0.0) + res.position
                counts[res.competitor] = counts.get(res.competitor, 0) + 1
    avg_pos = {c: sums[c] / counts[c] for c in sums}
    return avg_pos, counts


def _positional_stats(
    orders: list[list[str]], codes: list[str]
) -> tuple[dict[str, float], dict[str, int], dict[str, int]]:
    """Mean and 10th/90th-percentile finishing position from sampled orders."""
    idx = {c: i for i, c in enumerate(codes)}
    pos = np.empty((len(orders), len(codes)), dtype=float)
    for s, order in enumerate(orders):
        for p, c in enumerate(order, start=1):
            pos[s, idx[c]] = p
    mean = pos.mean(axis=0)
    p10 = np.percentile(pos, 10, axis=0)
    p90 = np.percentile(pos, 90, axis=0)
    mean_finish = {c: float(mean[i]) for c, i in idx.items()}
    range_low = {c: int(round(p10[i])) for c, i in idx.items()}
    range_high = {c: int(round(p90[i])) for c, i in idx.items()}
    return mean_finish, range_low, range_high


# --------------------------------------------------------------------------- #
# Skill estimation (leakage-safe) — replaces the old flat pace average
# --------------------------------------------------------------------------- #
def _elo_skill(source: F2DataSource, year: int, current_round: int) -> tuple[
    dict[str, float], dict[str, float]
]:
    """Replay prior sprint+feature races into Elo and snapshot driver/team ratings.

    Sprint and feature share a ``(season, round)``, which the Elo builder rejects
    (it demands strictly chronological events), so each weekend is encoded as two
    sub-rounds: sprint = ``2r-1``, feature = ``2r``. ``replay_history`` then
    enforces the prior-only cutoff at the boundary, exactly like
    :func:`leakage.assert_seasons_prior_only`.
    """
    builder = elo.EloFeatureBuilder()
    events: list[elo.RaceEvent] = []
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    for rnd in prior_rounds:
        races = source.race_results_for_round(year, rnd)
        for sub, race_type in ((2 * rnd - 1, SPRINT), (2 * rnd, FEATURE)):
            results = races[race_type]
            if not results:
                continue
            finish = {res.competitor: res.position for res in results}
            grid = {res.competitor: (res.grid or res.position) for res in results}
            events.append(
                elo.RaceEvent(
                    season=year,
                    round=sub,
                    finish_order=finish,
                    grid_order=grid,
                    team_of=config.TEAM_OF,
                )
            )
    # Cutoff is the sprint sub-round of the round being predicted: every prior
    # weekend (both races) is admitted, this round and beyond is rejected.
    builder.replay_history(events, current_season=year, current_round=2 * current_round - 1)
    builder.ensure_rookies(config.TEAM_OF)  # pool any never-seen driver to team mean

    teammate = _teammate_of()
    driver_elo: dict[str, float] = {}
    team_elo: dict[str, float] = {}
    for d in config.DRIVERS:
        code, team = d["code"], d["team"]
        feats = builder.features_for(code, team, teammate.get(code))
        driver_elo[code] = feats["driver_elo"]
        team_elo[code] = feats["team_elo"]
    return driver_elo, team_elo


def _bayesian_skill(
    source: F2DataSource, year: int, prior_rounds: list[int]
) -> dict[str, float] | None:
    """Optional driver-within-team Bayesian skill, or None when unavailable.

    Gated by ``config.USE_BAYESIAN_SKILL`` and the optional PyMC dependency. Any
    failure (flag off, PyMC missing, too little data) degrades silently to None
    so the Elo+history blend carries the model — the F1 optional-LSTM pattern.
    """
    if not config.USE_BAYESIAN_SKILL or not prior_rounds:
        return None
    try:
        from motorsport_core import hierarchical_bayes as hb

        rows: list[dict] = []
        for rnd in prior_rounds:
            races = source.race_results_for_round(year, rnd)
            for race in (races[SPRINT], races[FEATURE]):
                for res in race:
                    rows.append(
                        {
                            "season": year,
                            "round": rnd,
                            "driver": res.competitor,
                            "team": config.TEAM_OF.get(res.competitor, "?"),
                            "finish": res.position,
                        }
                    )
        posterior = hb.fit_hierarchical_skill_model(rows, method="advi")
        # Posterior δ_drv is a *deviation from the field mean* (higher = slower),
        # so negate to orient "higher = faster" like the other signals.
        return {d["code"]: -posterior.driver_skill_feature(d["code"]) for d in config.DRIVERS}
    except Exception:  # pragma: no cover - optional path, never breaks the run
        return None


def estimate_skill(
    source: F2DataSource, year: int, current_round: int
) -> dict[str, float]:
    """Per-driver latent pace (lower = faster) from leakage-safe prior signals.

    Blends Elo (driver + a small team component), smoothed finishing history, and
    an optional Bayesian prior — each standardised, oriented "higher = faster",
    weighted by :data:`config.SKILL_WEIGHTS`, then mapped onto the pace scale the
    Plackett-Luce sampler expects. With no prior rounds (round 1) every signal is
    flat, so every driver gets the neutral pace.
    """
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    # Leakage guard at the boundary: the aggregation set must be prior-only.
    leakage.assert_prior_only(
        {r: None for r in prior_rounds}, current_round=current_round, label="f2.model.skill"
    )

    codes = [d["code"] for d in config.DRIVERS]
    if not prior_rounds:
        return {c: config.PACE_BASE for c in codes}

    driver_elo, team_elo = _elo_skill(source, year, current_round)
    avg_pos, _counts = _prior_history(source, year, prior_rounds)
    field_mean_pos = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    # History oriented higher = faster (negate average position).
    history_signal = {c: -avg_pos.get(c, field_mean_pos) for c in codes}
    bayes_signal = _bayesian_skill(source, year, prior_rounds)

    z_elo = _zscores(driver_elo)
    z_team = _zscores(team_elo)
    z_hist = _zscores(history_signal)
    z_bayes = _zscores(bayes_signal) if bayes_signal else None

    w = config.SKILL_WEIGHTS
    pace: dict[str, float] = {}
    for c in codes:
        merit = w["elo"] * z_elo[c] + w["history"] * z_hist[c] + w["team"] * z_team[c]
        if z_bayes is not None:
            merit += w.get("bayes", 0.5) * z_bayes[c]
        # Higher merit (faster) → lower pace.
        pace[c] = config.PACE_BASE - config.PACE_SPREAD * merit
    return pace


def rookie_flags(source: F2DataSource, year: int, current_round: int) -> dict[str, bool]:
    """Which drivers are rookies (sparse prior history) at this round."""
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    _avg, counts = _prior_history(source, year, prior_rounds)
    return {
        d["code"]: counts.get(d["code"], 0) < config.ROOKIE_RACE_THRESHOLD
        for d in config.DRIVERS
    }


# --------------------------------------------------------------------------- #
# Race-type heads
# --------------------------------------------------------------------------- #
def _reverse_grid(merit_order: list[str]) -> list[str]:
    """F2 sprint grid: reverse the top ``REVERSE_GRID_SIZE`` of the merit order."""
    n = config.REVERSE_GRID_SIZE
    return merit_order[:n][::-1] + merit_order[n:]


def _race_forecast(
    race_type: str,
    grid: list[str],
    score: Mapping[str, float],
    *,
    n_samples: int,
) -> RaceForecast:
    """Run the Monte Carlo for one race from a per-driver score (lower = faster)."""
    markets = calibration.plackett_luce_probabilities(score, n_samples=n_samples)
    orders = calibration.sample_finishing_orders(score, n_samples=n_samples)
    codes = list(score.keys())
    mean_finish, range_low, range_high = _positional_stats(orders, codes)
    # Expected finishing order: by simulated mean position (lower = better).
    order = sorted(codes, key=lambda c: mean_finish[c])
    # Confidence label from the field-relative interval width (reuses core's bands).
    widths = [range_high[c] - range_low[c] for c in codes]
    labels = conformal.width_to_confidence_label(widths)
    confidence = {c: labels[i] for i, c in enumerate(codes)} if labels else {}
    return RaceForecast(
        race_type=race_type,
        grid=list(grid),
        order=order,
        score=dict(score),
        markets=markets,
        mean_finish=mean_finish,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        n_samples=markets.n_samples,
        temperature=markets.temperature,
    )


def forecast_round(
    source: F2DataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
) -> RoundForecastF2:
    """Full sprint + feature forecast for one round."""
    n_samples = n_samples or config.DEFAULT_SAMPLES
    pace = estimate_skill(source, year, round)
    venue = source._venue(round)

    # Feature: merit grid (fastest first), sampled from pace alone.
    merit_order = sorted(pace, key=lambda c: pace[c])
    feature = _race_forecast(FEATURE, merit_order, pace, n_samples=n_samples)

    # Sprint: reverse-grid start; a grid penalty makes track position matter so
    # the fast drivers who line up at the back must overtake.
    sprint_grid = _reverse_grid(merit_order)
    grid_pos = {c: i + 1 for i, c in enumerate(sprint_grid)}
    sprint_score = {c: pace[c] + config.SPRINT_GRID_PENALTY * grid_pos[c] for c in pace}
    sprint = _race_forecast(SPRINT, sprint_grid, sprint_score, n_samples=n_samples)

    return RoundForecastF2(
        season=year,
        round=round,
        venue_key=venue.key,
        venue_name=venue.name,
        country=venue.country,
        sprint=sprint,
        feature=feature,
    )


# --------------------------------------------------------------------------- #
# Championship Monte Carlo — F2-aware (alternates sprint + feature points)
# --------------------------------------------------------------------------- #
def project_championship_f2(
    current_points: Mapping[str, float],
    skill: Mapping[str, float],
    remaining_rounds: int,
    *,
    n_samples: int | None = None,
    seed: int = 42,
) -> list[TitleProjection]:
    """Title projection that scores each remaining round as sprint + feature.

    The shared :func:`motorsport_core.championship.project_championship` applies a
    single points table per race; F2 awards a different table to the sprint and
    the feature, so this thin local MC alternates them while still reusing the
    core Plackett-Luce sampler (no duplicated sampling logic).
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    competitors = list(skill.keys())
    idx = {c: i for i, c in enumerate(competitors)}
    base = np.array([float(current_points.get(c, 0.0)) for c in competitors], dtype=float)

    if remaining_rounds <= 0:
        return _summarize(competitors, current_points, base[None, :])

    total = n_samples * remaining_rounds
    sprint_orders = calibration.sample_finishing_orders(skill, n_samples=total, seed=seed)
    feature_orders = calibration.sample_finishing_orders(skill, n_samples=total, seed=seed + 1)

    sim = np.tile(base, (n_samples, 1))
    cursor = 0
    for _ in range(remaining_rounds):
        for s in range(n_samples):
            for pos, c in enumerate(sprint_orders[cursor], start=1):
                sim[s, idx[c]] += config.SPRINT_POINTS.get(pos, 0)
            for pos, c in enumerate(feature_orders[cursor], start=1):
                sim[s, idx[c]] += config.FEATURE_POINTS.get(pos, 0)
            cursor += 1
    return _summarize(competitors, current_points, sim)


def _summarize(
    competitors: list[str], current_points: Mapping[str, float], sim: np.ndarray
) -> list[TitleProjection]:
    n = sim.shape[0]
    winners = np.argmax(sim, axis=1)
    win_counts = np.bincount(winners, minlength=len(competitors))
    out: list[TitleProjection] = []
    for i, c in enumerate(competitors):
        col = sim[:, i]
        out.append(
            TitleProjection(
                key=c,
                p_title=float(win_counts[i] / n),
                current_points=float(current_points.get(c, 0.0)),
                proj_mean=float(col.mean()),
                proj_p10=float(np.percentile(col, 10)),
                proj_p90=float(np.percentile(col, 90)),
            )
        )
    out.sort(key=lambda t: -t.p_title)
    return out
