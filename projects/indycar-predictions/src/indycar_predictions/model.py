"""The IndyCar prediction model.

Three facts about IndyCar racing drive the design:

1. **Ovals and road/street courses are near-different sports.** The calendar
   alternates between pack-oval racing and braking-and-kerbs circuits, and the
   specialists differ. The model's dominant split is therefore a **dual Elo**:
   one :mod:`motorsport_core.elo` instance rated only on oval rounds, one
   rated only on road/street rounds (street and permanent road courses share a
   skill set far more than either shares with ovals), blended per-round by the
   round's track group next to an overall field Elo. Calibration is
   additionally stratified by the full three-way track type.
2. **Spec series, strong structure.** The DW12 is a spec chassis with two
   engine manufacturers and multi-car teams: driver skill dominates, the team
   effect is real (dampers/engineering) and the engine adds a smaller shared
   effect — so team and engine Elos ride next to the driver ratings.
3. **Attrition is first-class and track-dependent.** IndyCar classifies every
   car and ovals retire far more of the field than road courses (the curated
   status fields carry the signal). The race forecast **composes** a
   per-driver DNF hazard with the pace model: sample DNFs FIRST (Bernoulli per
   driver), rank the survivors by Plackett-Luce pace, send retirees to the
   back in random order — the composition pattern shared with the NASCAR
   project and the F1 candidate model.

The model estimates a leakage-safe *latent skill* per driver (blending the
Elo stack, current-season finishing history, and an optional gradient-boosted
signal), estimates a per-driver hazard from rolling status history +
per-track-type attrition, then runs the composed Monte Carlo for the round's
race. Post-qualifying, the forecast conditions on the real grid with a small
per-slot pace cost. Everything numerically heavy is reused from
``motorsport-core``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from motorsport_core import conformal, elo, leakage
from motorsport_core.calibration import DEFAULT_TEMPERATURE, MarketProbabilities
from motorsport_core.championship import TitleProjection

from . import config, ml_skill
from .datasource import IndycarDataSource

RACE = "race"


# --------------------------------------------------------------------------- #
# Output containers
# --------------------------------------------------------------------------- #
@dataclass
class RaceForecast:
    """Forecast for one round's race (DNF-composed Monte Carlo)."""

    race_type: str                      # always "race" (single-race rounds)
    grid: list[str]                     # codes in starting-grid order
    order: list[str]                    # expected finishing order (codes)
    score: dict[str, float]             # per-driver pace/score, lower = faster
    p_dnf: dict[str, float]             # per-driver retirement hazard, [0, 1]
    markets: MarketProbabilities        # win/podium/top6/top10 + H2H (composed)
    mean_finish: dict[str, float]       # MC mean finishing position
    range_low: dict[str, int]           # MC 10th-percentile finish (optimistic)
    range_high: dict[str, int]          # MC 90th-percentile finish (pessimistic)
    confidence: dict[str, str]          # "High" | "Medium" | "Low" per driver
    n_samples: int
    temperature: float


@dataclass
class RoundForecastIndycar:
    """One round's race forecast plus venue metadata.

    ``position_head`` records whether the opt-in finishing-position head
    (:mod:`.position_head`, A/B-gated by ``INDYCAR_USE_POSITION_HEAD``, default
    OFF) re-ranked this forecast: ``None`` = gate off (production path
    byte-identical), else a dict with ``applied`` plus either
    ``trainedRounds`` or a graceful-degradation ``reason``.
    """

    season: int
    round: int
    venue_key: str
    venue_name: str
    country: str | None
    track_type: str
    track_group: str
    race_name: str
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


def _prior_history(
    source: IndycarDataSource, year: int, prior_rounds: list[int]
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


# --------------------------------------------------------------------------- #
# Era helpers (config.INDYCAR_ERAS; core's table is F1-specific)
# --------------------------------------------------------------------------- #
def indycar_era_index(season: int) -> int | None:
    for i, (_name, start, end) in enumerate(config.INDYCAR_ERAS):
        if start <= season <= (end if end is not None else season):
            return i
    return None


def indycar_era_distance(season_a: int, season_b: int) -> int:
    """Era boundaries between two seasons (0 = same era); unknown → 0."""
    a, b = indycar_era_index(season_a), indycar_era_index(season_b)
    if a is None or b is None:
        return 0
    return abs(a - b)


def elo_seed_seasons(year: int, available: Iterable[int]) -> list[int]:
    """Prior seasons admitted into the Elo replay for a ``year`` forecast.

    Bounded below by ``config.ELO_FIRST_SEASON`` (2012 — the DW12
    introduction, the full curated history) and hard-cut at more than one era
    boundary back (the 2020 aeroscreen cut is handled by the Elo inter-season
    shrink; anything two boundaries away never contributes). Seasons at or
    after ``year`` are excluded (leakage).
    """
    return sorted(
        s
        for s in available
        if config.ELO_FIRST_SEASON <= s < year and indycar_era_distance(s, year) <= 1
    )


# --------------------------------------------------------------------------- #
# Elo stack (leakage-safe replay over the committed history files)
# --------------------------------------------------------------------------- #
def _ingest_pairwise(rater: elo.EloRating, finish_order: Mapping[str, int],
                     season: int, round_num: int) -> None:
    """All C(N,2) pairwise updates for one race (public-API replica of the
    core's internal race processor)."""
    keys = list(finish_order.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            pa, pb = finish_order[a], finish_order[b]
            score = 0.5 if pa == pb else (1.0 if pa < pb else 0.0)
            rater.update_pairwise(a, b, score, season, round_num)
    rater.commit_race_attendance(keys, season, round_num)


def _group_order(finish_order: Mapping[str, int], group_of: Mapping[str, str]) -> dict[str, int]:
    """Collapse a driver finish order into a group (team/engine) finish order
    by mean finishing position."""
    grouped: dict[str, list[int]] = {}
    for code, pos in finish_order.items():
        g = group_of.get(code)
        if g:
            grouped.setdefault(g, []).append(pos)
    means = sorted(((g, sum(v) / len(v)) for g, v in grouped.items()), key=lambda kv: kv[1])
    return {g: rank + 1 for rank, (g, _) in enumerate(means)}


def _season_events(source: IndycarDataSource, season: int, upto_round: int | None = None) -> list[dict]:
    """One event dict per completed round of ``season`` (< upto_round if given).

    Cached on the source (event construction walks the whole snapshot).
    """
    cache = source._model_cache
    key = ("events", season)
    if key not in cache:
        team_of = source.team_of(season)
        engine_of = source.engine_of(season)
        events: list[dict] = []
        for rnd in source.completed_rounds(season):
            results = source.results(season, rnd)
            if not results:
                continue
            events.append(
                {
                    "season": season,
                    "round": rnd,
                    "finish": {res.competitor: res.position for res in results},
                    "team_of": team_of,
                    "engine_of": engine_of,
                    "track_group": source.track_group_for(season, rnd),
                }
            )
        cache[key] = events
    events = cache[key]
    if upto_round is None:
        return events
    return [e for e in events if e["round"] < upto_round]


def _elo_skill(source: IndycarDataSource, year: int, current_round: int) -> dict:
    """Replay the Elo window (prior seasons + this season's prior rounds) and
    snapshot the full rating stack.

    Returns ``{"driver": {...}, "team": {...}, "engine": {...},
    "track": {group: {...}}, "career": {...}}`` where ``track`` carries the
    DUAL oval / road-street Elos. Prior seasons come from the committed
    history files (real data only — the synthetic generator never answers for
    a past season, so a missing file simply contributes nothing). The cutoff
    at ``(year, current_round)`` enforces the same prior-only discipline as
    ``leakage.assert_seasons_prior_only``. Cached on the source per
    (year, round) — replays are expensive.
    """
    cache = source._model_cache
    key = ("elo", year, current_round)
    if key in cache:
        return cache[key]

    # Incremental replay: the rating stack for (year, N) is the stack for
    # (year, M<N) plus the events of rounds [M, N). Walk-forward consumers
    # (export, backtests) ask in ascending round order, so we keep ONE live
    # rater state per season and only ingest the delta; a request behind the
    # state rebuilds from scratch (rare, still correct).
    state_key = ("elo_state", year)
    state = cache.get(state_key)
    if state is None or state["upto"] > current_round:
        state = {
            "driver": elo.DriverElo(),
            "team": elo.TeamElo(),
            "engine": elo.TeamElo(),
            "track": {g: elo.DriverElo() for g in config.ELO_TRACK_GROUPS},
            "career": {},
            "upto": 0,  # events with round < upto (this season) are ingested
            "seeded": False,
        }
        cache[state_key] = state

    events: list[dict] = []
    if not state["seeded"]:
        for season in elo_seed_seasons(year, range(config.ELO_FIRST_SEASON, year)):
            events.extend(_season_events(source, season))
        state["seeded"] = True
    events.extend(
        e
        for e in _season_events(source, year, upto_round=current_round)
        if e["round"] >= state["upto"]
    )

    driver, team, engine, track = state["driver"], state["team"], state["engine"], state["track"]
    career: dict[str, int] = state["career"]
    for ev in events:
        finish = ev["finish"]
        for code in finish:
            career[code] = career.get(code, 0) + 1
        _ingest_pairwise(driver, finish, ev["season"], ev["round"])
        _ingest_pairwise(team, _group_order(finish, ev["team_of"]), ev["season"], ev["round"])
        _ingest_pairwise(engine, _group_order(finish, ev["engine_of"]), ev["season"], ev["round"])
        group = ev.get("track_group", "road_street")
        _ingest_pairwise(track.get(group, track["road_street"]), finish, ev["season"], ev["round"])
    state["upto"] = current_round

    # Rookie pooling: never-seen drivers start at their team's mean rating.
    # (Snapshotted per request — never mutates the incremental raters.)
    team_of = source.team_of(year)
    team_ratings: dict[str, list[float]] = {}
    driver_ratings = driver.all_ratings()
    for code, t in team_of.items():
        if code in driver_ratings:
            team_ratings.setdefault(t, []).append(driver_ratings[code])
    for code, t in team_of.items():
        if code in driver_ratings:
            continue
        pool = team_ratings.get(t)
        driver_ratings[code] = (
            (sum(pool) / len(pool)) - elo.ROOKIE_TEAM_DISCOUNT
            if pool
            else elo.DEFAULT_RATING - elo.ROOKIE_TEAM_DISCOUNT
        )

    out = {
        "driver": driver_ratings,
        "team": team.all_ratings(),
        "engine": engine.all_ratings(),
        "track": {g: r.all_ratings() for g, r in track.items()},
        "career": dict(career),
    }
    cache[key] = out
    return out


# --------------------------------------------------------------------------- #
# Skill estimation (leakage-safe)
# --------------------------------------------------------------------------- #
def estimate_skill(
    source: IndycarDataSource, year: int, current_round: int
) -> dict[str, float]:
    """Per-driver latent pace (lower = faster) from leakage-safe prior signals.

    Blends the field-relative overall Elo, the DUAL oval/road-street Elo for
    this round's track group (the dominant weight), smoothed current-season
    finishing history, the team and engine Elos, and an optional
    gradient-boosted regressor (:mod:`.ml_skill`, 2019+ window only) — each
    standardised, oriented "higher = faster", weighted by
    :data:`config.SKILL_WEIGHTS`, then mapped onto the pace scale the sampler
    expects. Optional signals fold in only when available and degrade silently
    otherwise. At round 1 of a season with no prior-season history every
    signal is flat, so every driver gets neutral pace.
    """
    cache = source._model_cache
    ck = ("skill", year, current_round)
    if ck in cache:
        return dict(cache[ck])

    completed = source.completed_rounds(year)
    prior_rounds = [r for r in completed if r < current_round]
    # Leakage guard at the boundary: the aggregation set must be prior-only.
    leakage.assert_prior_only(
        {r: None for r in prior_rounds},
        current_round=current_round,
        label="indycar.model.skill",
    )

    codes = source.entrants(year, current_round)
    stack = _elo_skill(source, year, current_round)
    track_type = source.track_type_for(year, current_round)
    track_group = config.track_group_of(track_type)
    team_of = source.team_of(year)
    engine_of = source.engine_of(year)

    driver_elo = {c: stack["driver"].get(c, 1500.0) for c in codes}
    team_elo = {c: stack["team"].get(team_of.get(c, ""), 1500.0) for c in codes}
    engine_elo = {c: stack["engine"].get(engine_of.get(c, ""), 1500.0) for c in codes}
    track_elo = {c: stack["track"].get(track_group, {}).get(c, 1500.0) for c in codes}
    career = stack["career"]

    if not prior_rounds and not any(career.values()):
        out = {c: config.PACE_BASE for c in codes}
        cache[ck] = dict(out)
        return out

    avg_pos, _counts = _prior_history(source, year, prior_rounds)
    field_mean_pos = (sum(avg_pos.values()) / len(avg_pos)) if avg_pos else 0.0
    # History oriented higher = faster (negate average position).
    history_signal = {c: -avg_pos.get(c, field_mean_pos) for c in codes}
    # Learned GBR+XGB signal predicts mean finishing position (lower = faster);
    # negate to orient higher = faster. None when the ML path is off / deps
    # missing / too little data / pre-window season — then it isn't blended.
    ml_pred = ml_skill.predict_ml_skill(
        source, year, prior_rounds, driver_elo, field_mean_pos, track_type=track_type
    )
    ml_signal = {c: -ml_pred[c] for c in codes if c in ml_pred} if ml_pred else None

    z_elo = _zscores(driver_elo)
    z_track = _zscores(track_elo)
    z_team = _zscores(team_elo)
    z_engine = _zscores(engine_elo)
    z_hist = _zscores(history_signal)
    z_ml = _zscores({c: ml_signal.get(c, 0.0) for c in codes}) if ml_signal else None

    w = config.SKILL_WEIGHTS
    pace: dict[str, float] = {}
    for c in codes:
        merit = (
            w["elo"] * z_elo[c]
            + w["track_elo"] * z_track[c]
            + w["history"] * z_hist[c]
            + w["team"] * z_team[c]
            + w["engine"] * z_engine[c]
        )
        if z_ml is not None:
            merit += w.get("ml", 0.5) * z_ml[c]
        # Higher merit (faster) → lower pace.
        pace[c] = config.PACE_BASE - config.PACE_SPREAD * merit
    cache[ck] = dict(pace)
    return pace


def rookie_flags(source: IndycarDataSource, year: int, current_round: int) -> dict[str, bool]:
    """Which drivers are rookies (sparse IndyCar career) at this round."""
    career = _elo_skill(source, year, current_round)["career"]
    return {
        d["code"]: career.get(d["code"], 0) < config.ROOKIE_RACE_THRESHOLD
        for d in source.roster(year)
    }


# --------------------------------------------------------------------------- #
# DNF / attrition hazard (first-class model component)
# --------------------------------------------------------------------------- #
def _dnf_stats(source: IndycarDataSource, year: int, current_round: int) -> dict:
    """Rolling attrition tallies from prior data (this season's prior rounds +
    the previous season's history file). All prior-only by construction."""
    cache = source._model_cache
    key = ("dnf_stats", year, current_round)
    if key in cache:
        return cache[key]

    driver_starts: dict[str, int] = {}
    driver_dnfs: dict[str, int] = {}
    track_starts: dict[str, int] = {}
    track_dnfs: dict[str, int] = {}
    total_starts = 0
    total_dnfs = 0

    def _ingest(season: int, rounds: Iterable[int]) -> None:
        nonlocal total_starts, total_dnfs
        for rnd in rounds:
            rows = source.race_rows(season, rnd)
            if not rows:
                continue
            tt = source.track_type_for(season, rnd)
            for r in rows:
                dnf = bool(r.get("dnf"))
                code = r["code"]
                driver_starts[code] = driver_starts.get(code, 0) + 1
                driver_dnfs[code] = driver_dnfs.get(code, 0) + int(dnf)
                track_starts[tt] = track_starts.get(tt, 0) + 1
                track_dnfs[tt] = track_dnfs.get(tt, 0) + int(dnf)
                total_starts += 1
                total_dnfs += int(dnf)

    prev = year - 1
    if prev >= config.ELO_FIRST_SEASON:
        _ingest(prev, source.completed_rounds(prev))
    prior_rounds = [r for r in source.completed_rounds(year) if r < current_round]
    leakage.assert_prior_only(
        {r: None for r in prior_rounds},
        current_round=current_round,
        label="indycar.model.dnf",
    )
    _ingest(year, prior_rounds)

    out = {
        "driver_starts": driver_starts,
        "driver_dnfs": driver_dnfs,
        "track_starts": track_starts,
        "track_dnfs": track_dnfs,
        "total_starts": total_starts,
        "total_dnfs": total_dnfs,
    }
    cache[key] = out
    return out


def estimate_dnf_risk(
    source: IndycarDataSource, year: int, current_round: int
) -> dict[str, float]:
    """Per-driver P(DNF) for the round, composed from three shrunk rates.

    * season base rate (learned, shrunk toward the long-run IndyCar prior),
    * this round's **track-type attrition** (ovals run hotter — walls and
      pack racing; learned from the curated status fields),
    * the driver's own rolling incident rate (shrunk toward the track base).

    All inputs are strictly prior data. Bounded by ``config.DNF_CLIP`` so a
    cold start or a freak sample never produces a degenerate hazard.
    """
    stats = _dnf_stats(source, year, current_round)
    codes = source.entrants(year, current_round)
    track_type = source.track_type_for(year, current_round)

    n = stats["total_starts"]
    base = (
        (stats["total_dnfs"] + config.DNF_BASE_RATE_PRIOR * config.DNF_PRIOR_STRENGTH)
        / (n + config.DNF_PRIOR_STRENGTH)
        if n
        else config.DNF_BASE_RATE_PRIOR
    )
    t_starts = stats["track_starts"].get(track_type, 0)
    t_rate = (
        (stats["track_dnfs"].get(track_type, 0) + base * config.DNF_PRIOR_STRENGTH)
        / (t_starts + config.DNF_PRIOR_STRENGTH)
        if t_starts
        else base
    )
    track_base = config.DNF_TRACK_BLEND * t_rate + (1.0 - config.DNF_TRACK_BLEND) * base

    lo, hi = config.DNF_CLIP
    out: dict[str, float] = {}
    for c in codes:
        d_starts = stats["driver_starts"].get(c, 0)
        d_rate = (
            (stats["driver_dnfs"].get(c, 0) + track_base * config.DNF_K_DRIVER)
            / (d_starts + config.DNF_K_DRIVER)
        )
        p = (1.0 - config.DNF_DRIVER_BLEND) * track_base + config.DNF_DRIVER_BLEND * d_rate
        out[c] = float(np.clip(p, lo, hi))
    return out


# --------------------------------------------------------------------------- #
# DNF-composed race Monte Carlo
# --------------------------------------------------------------------------- #
def _composed_rankings(
    score: Mapping[str, float],
    p_dnf: Mapping[str, float],
    *,
    n_samples: int,
    temperature: float,
    seed: int,
) -> tuple[list[str], np.ndarray]:
    """Sample finishing orders with the DNF composition.

    Per sample: draw each driver's retirement (Bernoulli hazard), rank the
    survivors by Gumbel-perturbed Plackett-Luce strength (identical math to
    the core sampler), and fill the remaining positions with the retirees in
    random order (laps completed at retirement are unknowable pre-race).
    Returns ``(codes, rankings)`` where ``rankings[s, k]`` is the index of the
    driver finishing position ``k+1`` in sample ``s``.
    """
    codes = list(score.keys())
    times = np.array([float(score[c]) for c in codes], dtype=np.float64)
    lam = np.exp(-(times - times.min()) / float(temperature))
    log_lam = np.log(lam)
    rng = np.random.default_rng(seed)
    n = len(codes)
    u = rng.uniform(size=(n_samples, n))
    gumbel = -np.log(-np.log(u))
    perturbed = log_lam[None, :] + gumbel
    hazard = np.array([float(p_dnf.get(c, 0.0)) for c in codes], dtype=np.float64)
    dnf_mask = rng.random((n_samples, n)) < hazard[None, :]
    # Retirees sort after every survivor, ordered randomly among themselves.
    retiree_key = rng.uniform(size=(n_samples, n))
    key = np.where(dnf_mask, -1e9 + retiree_key, perturbed)
    return codes, np.argsort(-key, axis=1)


def _markets_from_rankings(
    codes: list[str], rankings: np.ndarray, *, temperature: float
) -> tuple[MarketProbabilities, np.ndarray]:
    """Empirical market probabilities + the positions matrix from samples.

    Same reduction as the core's Plackett-Luce market builder, applied to the
    composed samples so the probability layer reflects the DNF hazard.
    """
    n_samples, n = rankings.shape
    positions = np.empty_like(rankings)
    sample_idx = np.arange(n_samples)[:, None]
    positions[sample_idx, rankings] = np.arange(n)[None, :]

    p_win_arr = (positions == 0).mean(axis=0)
    p_podium_arr = (positions <= 2).mean(axis=0)
    p_top6_arr = (positions <= min(5, n - 1)).mean(axis=0)
    p_top10_arr = (positions <= min(9, n - 1)).mean(axis=0)

    ahead = (positions[:, :, None] < positions[:, None, :]).mean(axis=0)
    h2h: dict[str, dict[str, float]] = {}
    for i, di in enumerate(codes):
        h2h[di] = {dj: float(ahead[i, j]) for j, dj in enumerate(codes) if j != i}

    markets = MarketProbabilities(
        drivers=tuple(codes),
        p_win={c: float(p_win_arr[i]) for i, c in enumerate(codes)},
        p_podium={c: float(p_podium_arr[i]) for i, c in enumerate(codes)},
        p_top6={c: float(p_top6_arr[i]) for i, c in enumerate(codes)},
        p_top10={c: float(p_top10_arr[i]) for i, c in enumerate(codes)},
        h2h=h2h,
        n_samples=n_samples,
        temperature=temperature,
    )
    return markets, positions


def _race_forecast(
    race_type: str,
    grid: list[str],
    score: Mapping[str, float],
    p_dnf: Mapping[str, float],
    *,
    n_samples: int,
    temperature: float = DEFAULT_TEMPERATURE,
    seed: int = 42,
) -> RaceForecast:
    """Run the DNF-composed Monte Carlo for one race from a per-driver score
    (lower = faster) and hazard."""
    codes, rankings = _composed_rankings(
        score, p_dnf, n_samples=n_samples, temperature=temperature, seed=seed
    )
    markets, positions = _markets_from_rankings(codes, rankings, temperature=temperature)
    pos1 = positions + 1  # 1-indexed finishing positions
    mean = pos1.mean(axis=0)
    p10 = np.percentile(pos1, 10, axis=0)
    p90 = np.percentile(pos1, 90, axis=0)
    mean_finish = {c: float(mean[i]) for i, c in enumerate(codes)}
    range_low = {c: int(round(p10[i])) for i, c in enumerate(codes)}
    range_high = {c: int(round(p90[i])) for i, c in enumerate(codes)}
    order = sorted(codes, key=lambda c: mean_finish[c])
    widths = [range_high[c] - range_low[c] for c in codes]
    labels = conformal.width_to_confidence_label(widths)
    confidence = {c: labels[i] for i, c in enumerate(codes)} if labels else {}
    return RaceForecast(
        race_type=race_type,
        grid=list(grid),
        order=order,
        score=dict(score),
        p_dnf={c: float(p_dnf.get(c, 0.0)) for c in codes},
        markets=markets,
        mean_finish=mean_finish,
        range_low=range_low,
        range_high=range_high,
        confidence=confidence,
        n_samples=n_samples,
        temperature=temperature,
    )


# --------------------------------------------------------------------------- #
# Round forecast
# --------------------------------------------------------------------------- #
def _complete_grid(known_grid: list[str], merit_order: list[str]) -> list[str]:
    """Turn a real (possibly partial) qualifying order into a full grid
    permutation: keep the real order for the drivers it covers, drop unknown/
    duplicate codes, append the rest in predicted-merit order."""
    valid = set(merit_order)
    seen: set[str] = set()
    grid: list[str] = []
    for code in known_grid:
        if code in valid and code not in seen:
            grid.append(code)
            seen.add(code)
    grid.extend(c for c in merit_order if c not in seen)
    return grid


def forecast_round(
    source: IndycarDataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
    use_position_head: bool | None = None,
) -> RoundForecastIndycar:
    """Full forecast for one round's race.

    ``known_grid`` is the **actual qualifying order** (P1 first) when already
    published — the post-quali path. When given, the grid becomes the real
    grid and a small per-slot pace cost conditions the forecast on it. When
    ``None`` (pre-quali), the grid is the predicted merit order and the race
    is sampled from pace + hazard alone.

    ``use_position_head`` is the A/B gate for the opt-in finishing-position
    head: ``None`` (default) defers to the ``INDYCAR_USE_POSITION_HEAD`` env
    flag — **OFF by default** so the production path is untouched.
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    pace = estimate_skill(source, year, round)
    p_dnf = estimate_dnf_risk(source, year, round)
    venue = source.venue_for(year, round)
    meta = source.race_meta(year, round)
    track_type = source.track_type_for(year, round)

    merit_order = sorted(pace, key=lambda c: pace[c])
    if known_grid:
        grid = _complete_grid(known_grid, merit_order)
        g_pos = {c: i + 1 for i, c in enumerate(grid)}
        score = {c: pace[c] + config.GRID_WEIGHT * g_pos[c] for c in pace}
        race = _race_forecast(RACE, grid, score, p_dnf, n_samples=n_samples)
    else:
        race = _race_forecast(RACE, merit_order, pace, p_dnf, n_samples=n_samples)

    result = RoundForecastIndycar(
        season=year,
        round=round,
        venue_key=venue.key,
        venue_name=venue.name,
        country=venue.country,
        track_type=track_type,
        track_group=config.track_group_of(track_type),
        race_name=str(meta.get("raceName", "") or ""),
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
# Championship Monte Carlo (straight points — IndyCar has NO playoffs)
# --------------------------------------------------------------------------- #
def project_championship_indycar(
    current_points: Mapping[str, float],
    skill: Mapping[str, float],
    remaining_rounds: int,
    *,
    n_samples: int | None = None,
    seed: int = 42,
) -> list[TitleProjection]:
    """Title projection over the remaining rounds (one race each, cumulative
    points — most points after the finale wins; no playoffs, no resets).

    Race points come from sampled Plackett-Luce finishing orders (the shared
    core sampler). IndyCar also pays small bonuses (+1 pole, +1 for leading a
    lap, +2 most laps led) that depend on sessions the round model does not
    simulate, so each remaining round adds their *expectation* per driver,
    using the round win probability as the proxy (qualifying pace, early pace
    and race pace share one merit distribution) — the same honest fold the FE
    project uses for pole/fastest-lap. The 2026 curated data shows NO double
    points at the Indy 500 (``config.INDY500_DOUBLE_POINTS``), so no
    extra-race equivalent is needed; if a future season reinstates it, fold it
    here (per-project) — the core stays untouched.
    """
    n_samples = n_samples or config.DEFAULT_SAMPLES
    from motorsport_core import calibration

    competitors = list(skill.keys())
    idx = {c: i for i, c in enumerate(competitors)}
    base = np.array([float(current_points.get(c, 0.0)) for c in competitors], dtype=float)

    if remaining_rounds <= 0:
        return _summarize(competitors, current_points, base[None, :])

    n = len(competitors)
    race_pts = np.array(
        [config.POINTS.get(p, 5) for p in range(1, n + 1)], dtype=float
    )
    total = n_samples * remaining_rounds
    orders = calibration.sample_finishing_orders(skill, n_samples=total, seed=seed)
    rank = np.fromiter(
        (idx[c] for row in orders for c in row), dtype=np.int64, count=total * n
    ).reshape(total, n)
    positions = np.empty_like(rank)
    positions[np.arange(total)[:, None], rank] = np.arange(n)[None, :]

    # Expected bonus points per driver per round: pole + led-a-lap + most-laps
    # led, with p_win as the shared merit proxy (front-runners collect them).
    markets = calibration.plackett_luce_probabilities(skill, n_samples=2000, seed=seed + 1)
    bonus_per_round = np.array(
        [
            (config.POLE_BONUS + config.LED_LAP_BONUS + config.MOST_LAPS_LED_BONUS)
            * markets.p_win.get(c, 0.0)
            for c in competitors
        ],
        dtype=float,
    )

    sim = np.tile(base, (n_samples, 1))
    pts_by_pos = race_pts[positions].reshape(n_samples, remaining_rounds, n)
    sim += pts_by_pos.sum(axis=1)
    sim += bonus_per_round[None, :] * remaining_rounds
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
