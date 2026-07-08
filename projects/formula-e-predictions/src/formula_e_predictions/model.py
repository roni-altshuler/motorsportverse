"""The FE prediction model.

Three facts about Formula E drive the design:

1. **Driver over team.** The chassis/battery/tyre are spec and only the
   powertrain differs, so driver skill dominates and the team effect is real
   but modest — the F3 spec-series weighting, softened slightly for the
   manufacturer powertrains (``config.SKILL_WEIGHTS["team"]``).
2. **One race per round, stable veteran grid.** No sprint head; instead the
   grid barely changes between seasons, so prior seasons are genuinely
   informative. The Elo stack is seeded by replaying real prior seasons
   (``config.ELO_FIRST_SEASON`` onward, the Gen2+ era window — Gen1 is
   hard-cut, mirroring ``motorsport_core.era``'s max-era-distance semantics
   with FE's own era table in ``config.FE_ERAS``) before the current season's
   prior rounds. Learned regressors train only on the Gen3 window
   (``config.ML_FIRST_SEASON``).
3. **Street-circuit variance.** Most rounds run between walls; outcomes are
   noisier than permanent circuits. The model does NOT clamp for this — the
   venue kind is exported as a calibration stratum and the probability
   calibrator finds the variance honestly from real outcomes.

The model estimates a leakage-safe *latent skill* per driver (blending Elo,
current-season finishing history, an optional gradient-boosted signal, and an
optional Bayesian prior), then runs the shared Plackett-Luce Monte Carlo for
the round's single race. Post-qualifying, the forecast conditions on the real
grid with a moderate per-slot pace cost (track position matters on street
circuits). Everything numerically heavy is reused from ``motorsport-core``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from motorsport_core import calibration, conformal, elo, leakage
from motorsport_core.calibration import MarketProbabilities
from motorsport_core.championship import TitleProjection

from . import config, ml_skill
from .datasource import FEDataSource

RACE = "race"


def _kind_str(venue) -> str:
    """Venue kind as a plain string ("street" / "circuit"); enum-safe."""
    kind = getattr(venue, "kind", "street")
    return str(getattr(kind, "value", kind) or "street")


# --------------------------------------------------------------------------- #
# Output containers
# --------------------------------------------------------------------------- #
@dataclass
class RaceForecast:
    """Forecast for one round's race."""

    race_type: str                      # always "race" (single-race rounds)
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
class RoundForecastFE:
    """One round's race forecast plus venue metadata.

    ``position_head`` records whether the opt-in finishing-position head
    (:mod:`.position_head`, A/B-gated by the ``FE_USE_POSITION_HEAD`` env flag,
    default OFF) re-ranked this forecast: ``None`` = gate off (production path
    byte-identical), else a dict with ``applied`` plus either ``trainedRounds``
    or a graceful-degradation ``reason``.
    """

    season: int
    round: int
    venue_key: str
    venue_name: str
    country: str | None
    venue_kind: str
    race: RaceForecast
    position_head: dict | None = None


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


def _teammate_of(team_of: Mapping[str, str]) -> dict[str, str | None]:
    """Map each driver to their (single) teammate, for the Elo teammate delta."""
    by_team: dict[str, list[str]] = {}
    for code, team in team_of.items():
        by_team.setdefault(team, []).append(code)
    out: dict[str, str | None] = {}
    for codes in by_team.values():
        for c in codes:
            others = [o for o in codes if o != c]
            out[c] = others[0] if others else None
    return out


def _prior_history(
    source: FEDataSource, year: int, prior_rounds: list[int]
) -> tuple[dict[str, float], dict[str, int]]:
    """Mean finishing position and race count per driver over prior rounds."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for rnd in prior_rounds:
        for res in source.results(year, rnd):
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
# FE era helpers (config.FE_ERAS; core's table is F1-specific)
# --------------------------------------------------------------------------- #
def fe_era_index(season: int) -> int | None:
    """Index of the FE era containing ``season`` (None before Gen1)."""
    for i, (_name, start, end) in enumerate(config.FE_ERAS):
        if start <= season <= (end if end is not None else season):
            return i
    return None


def fe_era_distance(season_a: int, season_b: int) -> int:
    """Era boundaries between two FE seasons (0 = same era). Lenient like
    :func:`motorsport_core.era.era_distance`: unknown seasons → 0."""
    a, b = fe_era_index(season_a), fe_era_index(season_b)
    if a is None or b is None:
        return 0
    return abs(a - b)


def elo_seed_seasons(year: int, available: list[int]) -> list[int]:
    """Prior seasons admitted into the Elo replay for a ``year`` forecast.

    Hard-cuts by FE era distance (> 2 boundaries back never contributes, and
    ``config.ELO_FIRST_SEASON`` bounds the window regardless) — the FE
    application of core's ``DEFAULT_MAX_ERA_DISTANCE`` semantics. Seasons at
    or after ``year`` are excluded (leakage).
    """
    return sorted(
        s
        for s in available
        if config.ELO_FIRST_SEASON <= s < year and fe_era_distance(s, year) <= 2
    )


# --------------------------------------------------------------------------- #
# Skill estimation (leakage-safe)
# --------------------------------------------------------------------------- #
def _season_events(
    source: FEDataSource, season: int, upto_round: int | None = None
) -> list[elo.RaceEvent]:
    """One RaceEvent per completed round of ``season`` (< upto_round if given)."""
    team_of = source.team_of(season)
    events: list[elo.RaceEvent] = []
    for rnd in source.completed_rounds(season):
        if upto_round is not None and rnd >= upto_round:
            break
        results = source.results(season, rnd)
        if not results:
            continue
        finish = {res.competitor: res.position for res in results}
        grid = {res.competitor: (res.grid or res.position) for res in results}
        events.append(
            elo.RaceEvent(
                season=season,
                round=rnd,
                finish_order=finish,
                grid_order=grid,
                team_of=team_of,
            )
        )
    return events


def _elo_skill(
    source: FEDataSource, year: int, current_round: int
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    """Replay the Elo window (prior seasons + this season's prior rounds) and
    snapshot driver/team ratings plus career race counts.

    Prior seasons come from the committed per-season snapshots (real data
    only — the synthetic generator never answers for a past season, so a
    missing snapshot simply contributes nothing). The cutoff at
    ``(year, current_round)`` enforces the same prior-only discipline as
    :func:`leakage.assert_seasons_prior_only`.
    """
    builder = elo.EloFeatureBuilder()
    events: list[elo.RaceEvent] = []
    career_counts: dict[str, int] = {}
    for season in elo_seed_seasons(year, list(range(config.ELO_FIRST_SEASON, year))):
        events.extend(_season_events(source, season))
    events.extend(_season_events(source, year, upto_round=current_round))
    for ev in events:
        for code in ev.finish_order:
            career_counts[code] = career_counts.get(code, 0) + 1
    builder.replay_history(events, current_season=year, current_round=current_round)
    team_of = source.team_of(year)
    builder.ensure_rookies(team_of)  # pool any never-seen driver to team mean

    teammate = _teammate_of(team_of)
    driver_elo: dict[str, float] = {}
    team_elo: dict[str, float] = {}
    for d in source.roster(year):
        code, team = d["code"], d["team"]
        feats = builder.features_for(code, team, teammate.get(code))
        driver_elo[code] = feats["driver_elo"]
        team_elo[code] = feats["team_elo"]
    return driver_elo, team_elo, career_counts


def _bayesian_skill(
    source: FEDataSource, year: int, prior_rounds: list[int]
) -> dict[str, float] | None:
    """Optional driver-within-team Bayesian skill, or None when unavailable.

    Gated by ``config.USE_BAYESIAN_SKILL`` and the optional PyMC dependency.
    Any failure degrades silently to None so the Elo+history blend carries the
    model — the F1 optional-LSTM pattern.
    """
    if not config.USE_BAYESIAN_SKILL or not prior_rounds:
        return None
    try:
        from motorsport_core import hierarchical_bayes as hb

        team_of = source.team_of(year)
        rows: list[dict] = []
        for rnd in prior_rounds:
            for res in source.results(year, rnd):
                rows.append(
                    {
                        "season": year,
                        "round": rnd,
                        "driver": res.competitor,
                        "team": team_of.get(res.competitor, "?"),
                        "finish": res.position,
                    }
                )
        posterior = hb.fit_hierarchical_skill_model(rows, method="advi")
        # Posterior δ_drv is a deviation from the field mean (higher = slower),
        # so negate to orient "higher = faster" like the other signals.
        return {
            d["code"]: -posterior.driver_skill_feature(d["code"])
            for d in source.roster(year)
        }
    except Exception:  # pragma: no cover - optional path, never breaks the run
        return None


def estimate_skill(
    source: FEDataSource, year: int, current_round: int
) -> dict[str, float]:
    """Per-driver latent pace (lower = faster) from leakage-safe prior signals.

    Blends Elo (driver + a modest team component; seeded from real prior
    seasons in the era window), smoothed current-season finishing history, an
    optional gradient-boosted regressor (:mod:`.ml_skill`, Gen3-window only),
    and an optional Bayesian prior — each standardised, oriented "higher =
    faster", weighted by :data:`config.SKILL_WEIGHTS`, then mapped onto the
    pace scale the Plackett-Luce sampler expects. The optional signals fold in
    only when available and degrade silently otherwise. At round 1 of a season
    with no prior-season snapshots every signal is flat, so every driver gets
    neutral pace.
    """
    completed = source.completed_rounds(year)
    prior_rounds = [r for r in completed if r < current_round]
    # Leakage guard at the boundary: the aggregation set must be prior-only.
    leakage.assert_prior_only(
        {r: None for r in prior_rounds}, current_round=current_round, label="fe.model.skill"
    )

    codes = source.entrants(year, current_round)
    driver_elo, team_elo, career = _elo_skill(source, year, current_round)
    # Entrants outside the season roster (one-off substitutes) still need a
    # rating — neutral when never seen.
    for c in codes:
        driver_elo.setdefault(c, 1500.0)
        team_elo.setdefault(c, 1500.0)
    driver_elo = {c: driver_elo[c] for c in codes}
    team_elo = {c: team_elo[c] for c in codes}

    if not prior_rounds and not any(career.values()):
        return {c: config.PACE_BASE for c in codes}

    avg_pos, _counts = _prior_history(source, year, prior_rounds)
    field_mean_pos = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    # History oriented higher = faster (negate average position).
    history_signal = {c: -avg_pos.get(c, field_mean_pos) for c in codes}
    bayes_signal = _bayesian_skill(source, year, prior_rounds)
    # Learned GBR+XGB signal predicts mean finishing position (lower = faster);
    # negate to orient higher = faster. None when the ML path is off / deps
    # missing / too little data / pre-Gen3 season — then it isn't blended.
    ml_pred = ml_skill.predict_ml_skill(source, year, prior_rounds, driver_elo, field_mean_pos)
    ml_signal = {c: -ml_pred[c] for c in codes} if ml_pred else None

    z_elo = _zscores(driver_elo)
    z_team = _zscores(team_elo)
    z_hist = _zscores(history_signal)
    z_bayes = _zscores({c: bayes_signal.get(c, 0.0) for c in codes}) if bayes_signal else None
    z_ml = _zscores(ml_signal) if ml_signal else None

    w = config.SKILL_WEIGHTS
    pace: dict[str, float] = {}
    for c in codes:
        merit = w["elo"] * z_elo[c] + w["history"] * z_hist[c] + w["team"] * z_team[c]
        if z_bayes is not None:
            merit += w.get("bayes", 0.5) * z_bayes[c]
        if z_ml is not None:
            merit += w.get("ml", 0.5) * z_ml[c]
        # Higher merit (faster) → lower pace.
        pace[c] = config.PACE_BASE - config.PACE_SPREAD * merit
    return pace


def rookie_flags(source: FEDataSource, year: int, current_round: int) -> dict[str, bool]:
    """Which drivers are rookies (sparse career history) at this round.

    Career counts span the Elo window (prior seasons + this season's prior
    rounds) — FE's veteran grid means genuine rookies are rare.
    """
    _d, _t, career = _elo_skill(source, year, current_round)
    return {
        d["code"]: career.get(d["code"], 0) < config.ROOKIE_RACE_THRESHOLD
        for d in source.roster(year)
    }


# --------------------------------------------------------------------------- #
# Race head
# --------------------------------------------------------------------------- #
def _complete_grid(known_grid: list[str], merit_order: list[str]) -> list[str]:
    """Turn a real (possibly partial) qualifying order into a full grid
    permutation.

    Keep the real order for the drivers it covers, drop unknown/duplicate
    codes, then append any remaining drivers in predicted-merit order — so the
    grid is always a complete, valid permutation that uses real data wherever
    it exists.
    """
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
    # Confidence label from the field-relative interval width (core's bands).
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
    source: FEDataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
    use_position_head: bool | None = None,
) -> RoundForecastFE:
    """Full forecast for one round's race.

    ``known_grid`` is the **actual qualifying order** (P1 first) when already
    published — the post-quali path. When given, the grid becomes the real
    grid and a moderate per-slot pace cost conditions the forecast on it
    (track position is worth something real on FE's street circuits). When
    ``None`` (pre-quali), the grid is the predicted merit order and the race
    is sampled from pace alone.

    ``use_position_head`` is the A/B gate for the opt-in finishing-position
    head: ``None`` (default) defers to the ``FE_USE_POSITION_HEAD`` env flag —
    **OFF by default** so the production path is untouched; ``True``/``False``
    force it explicitly.
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    pace = estimate_skill(source, year, round)
    venue = source.venue_for(year, round)

    merit_order = sorted(pace, key=lambda c: pace[c])
    if known_grid:
        grid = _complete_grid(known_grid, merit_order)
        g_pos = {c: i + 1 for i, c in enumerate(grid)}
        score = {c: pace[c] + config.GRID_WEIGHT * g_pos[c] for c in pace}
        race = _race_forecast(RACE, grid, score, n_samples=n_samples)
    else:
        race = _race_forecast(RACE, merit_order, pace, n_samples=n_samples)

    result = RoundForecastFE(
        season=year,
        round=round,
        venue_key=venue.key,
        venue_name=venue.name,
        country=venue.country,
        venue_kind=_kind_str(venue),
        race=race,
    )

    # Opt-in finishing-position head (A/B-gated, default OFF). Imported lazily
    # so the production path never pays for it; any failure degrades silently.
    from . import position_head as _position_head

    if _position_head.head_enabled(use_position_head):
        try:
            result = _position_head.maybe_rerank_round(
                source, year, round, result, n_samples=n_samples
            )
        except Exception:  # pragma: no cover - optional path, never breaks a forecast
            pass
    return result


# --------------------------------------------------------------------------- #
# Championship Monte Carlo — FE-aware (adds expected pole/FL bonus points)
# --------------------------------------------------------------------------- #
def project_championship_fe(
    current_points: Mapping[str, float],
    skill: Mapping[str, float],
    remaining_rounds: int,
    *,
    n_samples: int | None = None,
    seed: int = 42,
) -> list[TitleProjection]:
    """Title projection over the remaining rounds (one race each).

    Race points come from sampled Plackett-Luce finishing orders (the shared
    core sampler). FE also pays **pole (+3)** and **fastest lap (+1)** — those
    depend on sessions the round model does not simulate, so each remaining
    round adds their *expectation* per driver, using the round win probability
    as the proxy for both (qualifying pace and race pace share one merit
    distribution). Deterministic, honest, and it keeps the points ceiling and
    the projections mutually consistent with :data:`config.POLE_POINTS` /
    :data:`config.FASTEST_LAP_POINTS`.
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    competitors = list(skill.keys())
    idx = {c: i for i, c in enumerate(competitors)}
    base = np.array([float(current_points.get(c, 0.0)) for c in competitors], dtype=float)

    if remaining_rounds <= 0:
        return _summarize(competitors, current_points, base[None, :])

    total = n_samples * remaining_rounds
    race_orders = calibration.sample_finishing_orders(skill, n_samples=total, seed=seed)
    markets = calibration.plackett_luce_probabilities(skill, n_samples=2000, seed=seed + 1)
    bonus_per_round = np.array(
        [
            (config.POLE_POINTS + config.FASTEST_LAP_POINTS) * markets.p_win.get(c, 0.0)
            for c in competitors
        ],
        dtype=float,
    )

    sim = np.tile(base, (n_samples, 1))
    cursor = 0
    for _ in range(remaining_rounds):
        for s in range(n_samples):
            for pos, c in enumerate(race_orders[cursor], start=1):
                sim[s, idx[c]] += config.POINTS.get(pos, 0)
            cursor += 1
        sim += bonus_per_round[None, :]
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
