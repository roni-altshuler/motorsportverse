"""The MotoGP prediction model.

Two facts about MotoGP drive the design, and both differ from the F3 template:

1. **Not a spec series.** The motorcycle matters — a factory Ducati is a genuinely
   faster tool than a satellite Honda — so the manufacturer effect is a first-class
   term in the skill blend (``SKILL_WEIGHTS['team']`` is large), not the rounding
   error it is in spec F3. Rider skill still dominates (Márquez drags a bike up the
   order) but the factory is weighted, not ignored.
2. **The Sprint shares the Grand Prix grid.** MotoGP's Saturday Sprint starts from
   the *same* qualifying grid as Sunday's race — there is no reverse grid. It is
   simply shorter, so it is higher-variance: same grid, a hotter Plackett-Luce
   temperature, a slightly stronger track-position term.

The model estimates a leakage-safe latent *pace* per rider by blending **cross-season**
Elo (riders carry form year to year), smoothed finishing history, and a manufacturer
term, then routes that pace through the two race heads. Everything numerically heavy
is reused from ``motorsport-core`` (Plackett-Luce sampler, Elo builder, conformal
bands); only the MotoGP-specific race logic lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from motorsport_core import calibration, conformal, elo, leakage
from motorsport_core.calibration import MarketProbabilities
from motorsport_core.championship import TitleProjection

from . import config
from .datasource import MotoGPDataSource

SPRINT = "sprint"
FEATURE = "feature"


@dataclass
class RaceForecast:
    race_type: str
    grid: list[str]
    order: list[str]
    score: dict[str, float]
    markets: MarketProbabilities
    mean_finish: dict[str, float]
    range_low: dict[str, int]
    range_high: dict[str, int]
    confidence: dict[str, str]
    n_samples: int
    temperature: float


@dataclass
class RoundForecast:
    season: int
    round: int
    venue_key: str
    venue_name: str
    country: str | None
    sprint: RaceForecast
    feature: RaceForecast


# --------------------------------------------------------------------------- #
def _zscores(values: Mapping[str, float]) -> dict[str, float]:
    keys = list(values.keys())
    arr = np.array([values[k] for k in keys], dtype=float)
    sd = float(arr.std())
    if sd <= 1e-9:
        return {k: 0.0 for k in keys}
    mu = float(arr.mean())
    return {k: (float(values[k]) - mu) / sd for k in keys}


def _teammate_of() -> dict[str, str | None]:
    """Riders sharing a manufacturer are 'teammates' for the Elo teammate delta."""
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
    source: MotoGPDataSource, year: int, prior_rounds: list[int]
) -> tuple[dict[str, float], dict[str, int]]:
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
    idx = {c: i for i, c in enumerate(codes)}
    pos = np.empty((len(orders), len(codes)), dtype=float)
    for s, order in enumerate(orders):
        for p, c in enumerate(order, start=1):
            pos[s, idx[c]] = p
    mean = pos.mean(axis=0)
    p10 = np.percentile(pos, 10, axis=0)
    p90 = np.percentile(pos, 90, axis=0)
    return (
        {c: float(mean[i]) for c, i in idx.items()},
        {c: int(round(p10[i])) for c, i in idx.items()},
        {c: int(round(p90[i])) for c, i in idx.items()},
    )


def _elo_skill(source: MotoGPDataSource, year: int, current_round: int) -> tuple[
    dict[str, float], dict[str, float]
]:
    """Replay the cross-season sprint+feature corpus into Elo, snapshot ratings.

    Each race is a sub-round (sprint = ``2r-1``, feature = ``2r``); prior seasons
    are admitted whole and the current season up to the forecast round exclusive,
    enforced by the builder's ``(season, round) >= cutoff`` leakage guard.
    """
    builder = elo.EloFeatureBuilder()
    events: list[elo.RaceEvent] = []
    for (yr, sub, _race_type, finish) in source.history_events(year, current_round):
        events.append(
            elo.RaceEvent(
                season=yr,
                round=sub,
                finish_order=finish,
                grid_order=finish,  # grid ~ merit; teammate/vs-field deltas dominate
                team_of=config.TEAM_OF,
            )
        )
    builder.replay_history(events, current_season=year, current_round=2 * current_round - 1)
    builder.ensure_rookies(config.TEAM_OF)

    teammate = _teammate_of()
    driver_elo: dict[str, float] = {}
    team_elo: dict[str, float] = {}
    for d in config.DRIVERS:
        feats = builder.features_for(d["code"], d["team"], teammate.get(d["code"]))
        driver_elo[d["code"]] = feats["driver_elo"]
        team_elo[d["code"]] = feats["team_elo"]
    return driver_elo, team_elo


def estimate_skill(
    source: MotoGPDataSource, year: int, current_round: int
) -> dict[str, float]:
    """Per-rider latent pace (lower = faster) from leakage-safe prior signals.

    Blends cross-season Elo (rider + a large manufacturer term), smoothed
    finishing history, mapped onto the pace scale the Plackett-Luce sampler reads.
    With no prior data every signal is flat and every rider gets neutral pace.
    """
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    leakage.assert_prior_only(
        {r: None for r in prior_rounds}, current_round=current_round, label="motogp.model.skill"
    )
    codes = [d["code"] for d in config.DRIVERS]

    driver_elo, team_elo = _elo_skill(source, year, current_round)
    avg_pos, _counts = _prior_history(source, year, prior_rounds)
    # cross-season history: if this season has no prior rounds, fall back to the
    # rider's most recent prior-season average so early-season isn't blind.
    if not avg_pos:
        for y in reversed(config.HISTORY_SEASONS):
            snap = config.load_snapshot(y)
            n = len(snap.get("results", {}))
            if n:
                avg_pos, _counts = _prior_history(source, y, list(range(1, n + 1)))
                break
    field_mean = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    history_signal = {c: -avg_pos.get(c, field_mean) for c in codes}

    z_elo = _zscores(driver_elo)
    z_team = _zscores(team_elo)
    z_hist = _zscores(history_signal)
    w = config.SKILL_WEIGHTS
    pace: dict[str, float] = {}
    for c in codes:
        merit = w["elo"] * z_elo[c] + w["history"] * z_hist[c] + w["team"] * z_team[c]
        pace[c] = config.PACE_BASE - config.PACE_SPREAD * merit
    return pace


def rookie_flags(source: MotoGPDataSource, year: int, current_round: int) -> dict[str, bool]:
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    _avg, counts = _prior_history(source, year, prior_rounds)
    return {
        d["code"]: counts.get(d["code"], 0) < config.ROOKIE_RACE_THRESHOLD
        for d in config.DRIVERS
    }


# --------------------------------------------------------------------------- #
def _complete_grid(known_grid: list[str], merit_order: list[str]) -> list[str]:
    valid = set(merit_order)
    seen: set[str] = set()
    grid: list[str] = []
    for code in known_grid:
        if code in valid and code not in seen:
            grid.append(code)
            seen.add(code)
    grid.extend(c for c in merit_order if c not in seen)
    return grid


def _race_forecast(
    race_type: str, grid: list[str], score: Mapping[str, float], *, n_samples: int,
    temperature: float,
) -> RaceForecast:
    markets = calibration.plackett_luce_probabilities(
        score, n_samples=n_samples, temperature=temperature
    )
    orders = calibration.sample_finishing_orders(
        score, n_samples=n_samples, temperature=temperature
    )
    codes = list(score.keys())
    mean_finish, range_low, range_high = _positional_stats(orders, codes)
    order = sorted(codes, key=lambda c: mean_finish[c])
    widths = [range_high[c] - range_low[c] for c in codes]
    labels = conformal.width_to_confidence_label(widths)
    confidence = {c: labels[i] for i, c in enumerate(codes)} if labels else {}
    return RaceForecast(
        race_type=race_type, grid=list(grid), order=order, score=dict(score),
        markets=markets, mean_finish=mean_finish, range_low=range_low,
        range_high=range_high, confidence=confidence,
        n_samples=markets.n_samples, temperature=markets.temperature,
    )


def forecast_round(
    source: MotoGPDataSource, year: int, round: int, *,
    n_samples: int | None = None, known_grid: list[str] | None = None,
) -> RoundForecast:
    """Sprint + Grand Prix forecast for one round.

    ``known_grid`` is the real qualifying order (P1 first) once published — both
    heads then condition on the actual grid (MotoGP's Sprint and GP share it). When
    ``None`` (pre-quali) both heads use the predicted merit order. The Sprint runs a
    hotter temperature than the GP to reflect its shorter, higher-variance nature.
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    pace = estimate_skill(source, year, round)
    venue = source._venue(round)
    merit_order = sorted(pace, key=lambda c: pace[c])
    grid = _complete_grid(known_grid, merit_order) if known_grid else merit_order
    grid_pos = {c: i + 1 for i, c in enumerate(grid)}

    # Grand Prix (feature): merit or real grid, gentle grid-position term post-quali.
    feature_score = (
        {c: pace[c] + config.GRID_WEIGHT * grid_pos[c] for c in pace} if known_grid else pace
    )
    feature = _race_forecast(
        FEATURE, grid, feature_score, n_samples=n_samples, temperature=0.5,
    )
    # Sprint: SAME grid, shorter/higher-variance → hotter temperature.
    sprint_score = (
        {c: pace[c] + config.GRID_WEIGHT * grid_pos[c] for c in pace} if known_grid else pace
    )
    sprint = _race_forecast(
        SPRINT, grid, sprint_score, n_samples=n_samples,
        temperature=0.5 + config.SPRINT_TEMPERATURE_BOOST,
    )
    return RoundForecast(
        season=year, round=round, venue_key=venue.key, venue_name=venue.name,
        country=venue.country, sprint=sprint, feature=feature,
    )


# --------------------------------------------------------------------------- #
def project_championship_motogp(
    current_points: Mapping[str, float], skill: Mapping[str, float], remaining_rounds: int,
    *, n_samples: int | None = None, seed: int = 42,
) -> list[TitleProjection]:
    """Rider title projection scoring each remaining round as Sprint + Grand Prix."""
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
    win_counts = np.bincount(np.argmax(sim, axis=1), minlength=len(competitors))
    out = [
        TitleProjection(
            key=c, p_title=float(win_counts[i] / n),
            current_points=float(current_points.get(c, 0.0)),
            proj_mean=float(sim[:, i].mean()),
            proj_p10=float(np.percentile(sim[:, i], 10)),
            proj_p90=float(np.percentile(sim[:, i], 90)),
        )
        for i, c in enumerate(competitors)
    ]
    out.sort(key=lambda t: -t.p_title)
    return out
