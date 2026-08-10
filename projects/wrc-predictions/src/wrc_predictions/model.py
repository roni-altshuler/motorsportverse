"""The WRC prediction model.

Rally is not circuit racing, and two facts drive the design:

1. **One classification per round.** A rally is a single finishing order (no
   sprint, no qualifying grid), so the model has one race head: it estimates a
   leakage-safe latent *pace* per crew and samples the rally classification from
   it. There is no grid to condition on.
2. **The surface is (almost) the sport.** Gravel, tarmac and snow reward
   different crews; a Monte-Carlo/snow ace is not a Safari/rough-gravel ace. So
   the pace blend carries a **same-surface form** term alongside cross-season Elo,
   the car (manufacturer/tier), and recent finishing history.

Everything numerically heavy is reused from ``motorsport-core`` (Plackett-Luce
sampler, Elo builder, conformal bands, leakage guard); only the surface signal and
the single-race rally logic are WRC-specific.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from motorsport_core import calibration, conformal, elo, leakage
from motorsport_core.calibration import MarketProbabilities
from motorsport_core.championship import TitleProjection

from . import config
from .datasource import WrcDataSource


@dataclass
class RallyForecast:
    surface: str
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
    surface: str
    rally: RallyForecast


def _zscores(values: Mapping[str, float]) -> dict[str, float]:
    keys = list(values.keys())
    arr = np.array([values[k] for k in keys], dtype=float)
    sd = float(arr.std())
    if sd <= 1e-9:
        return {k: 0.0 for k in keys}
    mu = float(arr.mean())
    return {k: (float(values[k]) - mu) / sd for k in keys}


def _teammate_of() -> dict[str, str | None]:
    by_team: dict[str, list[str]] = {}
    for code, team in config.TEAM_OF.items():
        by_team.setdefault(team, []).append(code)
    out: dict[str, str | None] = {}
    for codes in by_team.values():
        for c in codes:
            others = [o for o in codes if o != c]
            out[c] = others[0] if others else None
    return out


def _prior_history(source: WrcDataSource, year: int, prior_rounds: list[int]):
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rnd in prior_rounds:
        for res in source.results(year, rnd):
            sums[res.competitor] = sums.get(res.competitor, 0.0) + res.position
            counts[res.competitor] = counts.get(res.competitor, 0) + 1
    avg = {c: sums[c] / counts[c] for c in sums}
    return avg, counts


def _positional_stats(orders, codes):
    idx = {c: i for i, c in enumerate(codes)}
    pos = np.empty((len(orders), len(codes)), dtype=float)
    for s, order in enumerate(orders):
        for p, c in enumerate(order, start=1):
            pos[s, idx[c]] = p
    mean, p10, p90 = pos.mean(0), np.percentile(pos, 10, 0), np.percentile(pos, 90, 0)
    return ({c: float(mean[i]) for c, i in idx.items()},
            {c: int(round(p10[i])) for c, i in idx.items()},
            {c: int(round(p90[i])) for c, i in idx.items()})


def _elo_skill(source: WrcDataSource, year: int, current_round: int):
    builder = elo.EloFeatureBuilder()
    events = [
        elo.RaceEvent(season=yr, round=rnd, finish_order=finish, grid_order=finish,
                      team_of=config.TEAM_OF)
        for (yr, rnd, finish) in source.history_events(year, current_round)
    ]
    builder.replay_history(events, current_season=year, current_round=current_round)
    builder.ensure_rookies(config.TEAM_OF)
    teammate = _teammate_of()
    driver_elo, team_elo = {}, {}
    for d in config.DRIVERS:
        feats = builder.features_for(d["code"], d["team"], teammate.get(d["code"]))
        driver_elo[d["code"]] = feats["driver_elo"]
        team_elo[d["code"]] = feats["team_elo"]
    return driver_elo, team_elo


def _surface_signal(source: WrcDataSource, year: int, current_round: int, surface: str):
    """Per-driver mean finishing position on the round's surface (prior rallies),
    oriented higher = faster. Neutral for crews with no same-surface history."""
    hist = source.surface_history(year, current_round).get(surface, {})
    codes = [d["code"] for d in config.DRIVERS]
    avg = {c: (sum(hist[c]) / len(hist[c])) for c in hist if hist[c]}
    field_mean = (sum(avg.values()) / len(avg)) if avg else 0.0
    return {c: -avg.get(c, field_mean) for c in codes}


def estimate_skill(source: WrcDataSource, year: int, current_round: int) -> dict[str, float]:
    prior_rounds = [r for r in range(1, config.COMPLETED_ROUNDS + 1) if r < current_round]
    leakage.assert_prior_only({r: None for r in prior_rounds},
                              current_round=current_round, label="wrc.model.skill")
    codes = [d["code"] for d in config.DRIVERS]

    driver_elo, team_elo = _elo_skill(source, year, current_round)
    avg_pos, _c = _prior_history(source, year, prior_rounds)
    if not avg_pos:  # early season: fall back to the most recent prior season
        for y in reversed(config.HISTORY_SEASONS):
            snap = config.load_snapshot(y)
            if snap.get("results"):
                avg_pos, _c = _prior_history(source, y, sorted(int(k) for k in snap["results"]))
                break
    field_mean = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    history_signal = {c: -avg_pos.get(c, field_mean) for c in codes}
    surface_signal = _surface_signal(source, year, current_round,
                                     config.surface_for_round(current_round))

    z_elo, z_team = _zscores(driver_elo), _zscores(team_elo)
    z_hist, z_surf = _zscores(history_signal), _zscores(surface_signal)
    w = config.SKILL_WEIGHTS
    pace = {}
    for c in codes:
        merit = (w["elo"] * z_elo[c] + w["history"] * z_hist[c]
                 + w["team"] * z_team[c] + w["surface"] * z_surf[c])
        pace[c] = config.PACE_BASE - config.PACE_SPREAD * merit
    return pace


def _championship_form(source: WrcDataSource, year: int, current_round: int, codes: list[str]):
    """Championship-form prior for the ensemble: probabilities from the current
    standings order (geometric decay). Uses this season's accumulated points before
    the round; before any round has run, falls back to the most recent prior
    season's final standings order. Leakage-safe (prior rounds only)."""
    pts = {c: 0.0 for c in codes}
    scored = False
    for rr in range(1, current_round):
        for res in source.results(year, rr):
            if res.competitor in pts:
                pts[res.competitor] += config.FEATURE_POINTS.get(res.position, 0)
                scored = True
    if not scored:
        for y in reversed(config.HISTORY_SEASONS):
            snap = config.load_snapshot(y)
            if snap.get("driverStandings"):
                rank = {d["code"]: i for i, d in enumerate(snap["driverStandings"])}
                pts = {c: -float(rank.get(c, len(codes))) for c in codes}
                break
    order = sorted(codes, key=lambda c: -pts[c])
    n = len(order)
    dec = np.array([config.FORM_DECAY ** i for i in range(n)], dtype=float)
    dec = dec / dec.sum()
    win = {c: float(dec[i]) for i, c in enumerate(order)}

    def topk(k, hi, mid, lo):
        return {c: (hi if i < k else mid if i < k + 3 else lo) for i, c in enumerate(order)}

    form_rank = {c: i for i, c in enumerate(order)}
    return win, topk(3, 0.7, 0.15, 0.03), topk(6, 0.85, 0.4, 0.08), topk(10, 0.9, 0.55, 0.15), form_rank


def forecast_round(source: WrcDataSource, year: int, round: int, *,
                   n_samples: int | None = None) -> RoundForecast:
    n_samples = n_samples or config.DEFAULT_SAMPLES
    pace = estimate_skill(source, year, round)
    venue = source._venue(round)
    surface = config.surface_for_round(round)
    codes = list(pace.keys())

    model_mk = calibration.plackett_luce_probabilities(pace, n_samples=n_samples)
    orders = calibration.sample_finishing_orders(pace, n_samples=n_samples)
    mean_finish, range_low, range_high = _positional_stats(orders, codes)

    # Ensemble the skill model with the championship-form prior (see config).
    a = config.ENSEMBLE_MODEL_WEIGHT
    f_win, f_pod, f_t6, f_t10, f_rank = _championship_form(source, year, round, codes)

    def blend(mdict, fdict, *, normalise=False):
        out = {c: a * float(mdict.get(c, 0.0)) + (1 - a) * float(fdict.get(c, 0.0)) for c in codes}
        if normalise:
            s = sum(out.values()) or 1.0
            out = {c: v / s for c, v in out.items()}
        return out

    markets = MarketProbabilities(
        drivers=list(codes),
        p_win=blend(model_mk.p_win, f_win, normalise=True),
        p_podium=blend(model_mk.p_podium, f_pod),
        p_top6=blend(model_mk.p_top6, f_t6),
        p_top10=blend(model_mk.p_top10, f_t10),
        h2h=model_mk.h2h,
        n_samples=model_mk.n_samples,
        temperature=model_mk.temperature,
    )
    # Expected order blends the model's simulated mean finish with the form rank.
    ens_rank = {c: a * mean_finish[c] + (1 - a) * (f_rank[c] + 1) for c in codes}
    order = sorted(codes, key=lambda c: ens_rank[c])

    widths = [range_high[c] - range_low[c] for c in codes]
    labels = conformal.width_to_confidence_label(widths)
    confidence = {c: labels[i] for i, c in enumerate(codes)} if labels else {}
    rally = RallyForecast(
        surface=surface, order=order, score=dict(pace), markets=markets,
        mean_finish=mean_finish, range_low=range_low, range_high=range_high,
        confidence=confidence, n_samples=markets.n_samples, temperature=markets.temperature,
    )
    return RoundForecast(season=year, round=round, venue_key=venue.key, venue_name=venue.name,
                         country=venue.country, surface=surface, rally=rally)


def project_championship_wrc(current_points, skill, remaining_rounds, *,
                             n_samples: int | None = None, seed: int = 42) -> list[TitleProjection]:
    n_samples = n_samples or config.DEFAULT_SAMPLES
    competitors = list(skill.keys())
    idx = {c: i for i, c in enumerate(competitors)}
    base = np.array([float(current_points.get(c, 0.0)) for c in competitors], dtype=float)
    if remaining_rounds <= 0:
        return _summarize(competitors, current_points, base[None, :])
    total = n_samples * remaining_rounds
    orders = calibration.sample_finishing_orders(skill, n_samples=total, seed=seed)
    sim = np.tile(base, (n_samples, 1))
    cursor = 0
    for _ in range(remaining_rounds):
        for s in range(n_samples):
            for pos, c in enumerate(orders[cursor], start=1):
                sim[s, idx[c]] += config.FEATURE_POINTS.get(pos, 0)
            cursor += 1
    return _summarize(competitors, current_points, sim)


def _summarize(competitors, current_points, sim) -> list[TitleProjection]:
    n = sim.shape[0]
    win_counts = np.bincount(np.argmax(sim, axis=1), minlength=len(competitors))
    out = [TitleProjection(key=c, p_title=float(win_counts[i] / n),
                           current_points=float(current_points.get(c, 0.0)),
                           proj_mean=float(sim[:, i].mean()),
                           proj_p10=float(np.percentile(sim[:, i], 10)),
                           proj_p90=float(np.percentile(sim[:, i], 90)))
           for i, c in enumerate(competitors)]
    out.sort(key=lambda t: -t.p_title)
    return out
