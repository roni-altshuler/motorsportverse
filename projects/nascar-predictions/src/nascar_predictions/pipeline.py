"""NASCAR prediction pipeline — orchestration over the Cup model and shared core.

This is where NASCAR reuses the shared core:

- **standings** → the committed snapshot carries the **official-feed-derived**
  standings (exact totals incl. stage points, from summing the feed's
  ``points_earned``); ``motorsport_core.standings`` provides the recomputed
  fallback (race points only — an approximation, used for synthetic runs).
- **skill + per-round forecast** → :mod:`nascar_predictions.model` (the Cup
  model: field-relative + per-track-type Elo blend → DNF-composed race head).
- **championship** → :func:`championship_playoffs.project_playoffs` with
  :data:`config.CUP_CHASE_FORMAT_2026` — title odds route through the REAL
  format (points reset, staggered seeding, 10-race Chase), never a naive
  cumulative-points Monte Carlo. The season state (points/wins/stage wins,
  and the reconstructed playoff phase once the Chase starts) is derived from
  the committed snapshot by :func:`build_season_state`, which also serves the
  2017-2025 elimination-format playoff backtest.

The only NASCAR-domain logic lives in :mod:`config` (points, formats,
calendar, roster, track types) and :mod:`model`; everything numerically heavy
is core or the config-driven playoff engine.
"""
from __future__ import annotations

from dataclasses import dataclass

from motorsport_core import championship, standings

from . import config, model
from .championship_playoffs import DriverState, PlayoffFormat, PlayoffPhaseState, SeasonState
from .championship_playoffs import project_playoffs as _project_playoffs
from .datasource import NascarDataSource
from .sources.composite import CompositeNascarSource
from .sources.snapshot import load_snapshot


# --------------------------------------------------------------------------- #
# Standings (official snapshot when real; core recompute otherwise)
# --------------------------------------------------------------------------- #
def _completed_races(source: NascarDataSource, year: int) -> list[dict[str, int]]:
    """{code: position} per completed round."""
    return [
        {r.competitor: r.position for r in source.results(year, rnd)}
        for rnd in source.completed_rounds(year)
    ]


def official_standings(source: NascarDataSource, year: int = 0) -> dict | None:
    """The official snapshot, but only when the source is actually serving
    real data (so synthetic-only unit tests fall back to computed standings).

    Race classifications alone omit stage points, so recomputed totals drift
    from the official table. The committed snapshot carries exact totals
    (summed from the feed's per-race ``points_earned``, which includes stage
    points) plus wins/stage-wins/points history — use them for the public
    standings and the championship's current state.
    """
    year = year or config.SEASON
    snap = load_snapshot(year)
    if not snap or snap.get("season") != year:
        return None
    try:
        prov = source.provenance(year, 1)
    except Exception:
        prov = "unknown"
    return snap if CompositeNascarSource.is_real(prov) else None


def driver_standings(source: NascarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_driver_standings(races, config.POINTS)


def current_driver_points(source: NascarDataSource, year: int = 0) -> dict[str, float]:
    """Authoritative current driver points: official totals if the feed is
    real, else recomputed from race results (race points only)."""
    year = year or config.SEASON
    official = official_standings(source, year)
    if official:
        return {d["code"]: float(d["points"]) for d in official.get("driverStandings", [])}
    return {row.key: row.points for row in driver_standings(source, year)}


def team_standings(source: NascarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_team_standings(races, config.POINTS, source.team_of(year))


def manufacturer_standings(source: NascarDataSource, year: int = 0) -> list[standings.StandingRow]:
    year = year or config.SEASON
    races = _completed_races(source, year)
    return standings.compute_team_standings(races, config.POINTS, source.make_of(year))


# --------------------------------------------------------------------------- #
# Per-round scoring tallies (feed the playoff state builder)
# --------------------------------------------------------------------------- #
def round_tallies(source: NascarDataSource, year: int, rnd: int) -> dict | None:
    """Actual scoring facts of one completed round.

    ``{"points": {code: race+stage points earned}, "winner": code,
    "stage_winners": [codes], "playoff_points": {code: pp earned}}``.
    Points come straight from the feed rows (``points_earned`` includes stage
    points — verified against 2026 totals), so reconstructed standings match
    the official table exactly.
    """
    rows = source.race_rows(year, rnd)
    if not rows:
        results = source.results(year, rnd)
        if not results:
            return None
        # Synthetic fallback: race points from the table, no stage data.
        points = {
            r.competitor: float(config.POINTS.get(r.position, 1)) for r in results if r.position
        }
        winner = next((r.competitor for r in results if r.position == 1), None)
        return {"points": points, "winner": winner, "stage_winners": [], "playoff_points": {}}
    points = {r["code"]: float(r.get("points") or 0.0) for r in rows}
    winner = next((r["code"] for r in rows if r.get("position") == 1), None)
    pp = {
        r["code"]: float(r.get("playoffPoints") or 0.0)
        for r in rows
        if r.get("playoffPoints")
    }
    stage_winners = []
    for stage_rows in (source.stage_results(year, rnd) or {}).values():
        w = next((s["code"] for s in stage_rows if s.get("position") == 1), None)
        if w:
            stage_winners.append(w)
    return {
        "points": points,
        "winner": winner,
        "stage_winners": stage_winners,
        "playoff_points": pp,
    }


# --------------------------------------------------------------------------- #
# Season state (regular season or reconstructed playoff phase)
# --------------------------------------------------------------------------- #
def _qualification_order(
    tallies: dict[str, DriverState], fmt: PlayoffFormat
) -> list[str]:
    """Playoff qualification order per the format's rule (mirrors the engine)."""
    if fmt.qualification == "wins_first":
        key = lambda c: (  # noqa: E731
            1 if tallies[c].wins > 0 else 0,
            tallies[c].wins,
            tallies[c].points,
        )
    else:
        key = lambda c: (tallies[c].points, tallies[c].wins)  # noqa: E731
    return sorted(tallies, key=key, reverse=True)


def build_season_state(
    source: NascarDataSource,
    year: int,
    fmt: PlayoffFormat,
    through_round: int | None = None,
) -> tuple[SeasonState, int]:
    """Season state as of ``through_round`` (default: all completed rounds).

    Returns ``(state, remaining_regular_season_races)`` ready for
    :func:`championship_playoffs.project_playoffs`:

    * inside the regular season: per-driver tallies + the remaining count;
    * at/after the playoff cut: the regular-season top-10 playoff-point bonus
      is applied (the engine's already-complete convention) and the playoff
      phase — alive set, reset/seeded round points, banked playoff points,
      round wins — is **reconstructed deterministically from the actual race
      results**, walking the format's rounds exactly like the simulator does.

    The reconstruction mirrors the engine's qualification rule (win-and-in
    fine print like the top-30 clause is intentionally out of scope — a
    documented simplification shared with the simulator).
    """
    completed = source.completed_rounds(year)
    through = through_round if through_round is not None else (max(completed) if completed else 0)
    rounds = [r for r in completed if r <= through]
    per_round = {r: round_tallies(source, year, r) for r in rounds}
    per_round = {r: t for r, t in per_round.items() if t}

    # Playoff-point availability seam: the 2018-2019 feeds carry neither
    # ``playoff_points_earned`` nor ``stage_results``, so for those seasons the
    # bank is reconstructed from the format constants (5 per win + 1 per known
    # stage win) — the stage-win playoff points are honestly missing pre-2020
    # and the playoff backtest reports that caveat.
    has_pp_data = any(t["playoff_points"] for t in per_round.values())
    if not has_pp_data and fmt.win_playoff_points:
        for t in per_round.values():
            pp: dict[str, float] = {}
            if t["winner"]:
                pp[t["winner"]] = pp.get(t["winner"], 0.0) + float(fmt.win_playoff_points)
            for c in t["stage_winners"]:
                pp[c] = pp.get(c, 0.0) + float(fmt.stage_win_playoff_points)
            t["playoff_points"] = pp

    reg = fmt.regular_season_races
    reg_rounds = [r for r in rounds if r <= reg]

    # --- cumulative driver tallies ---------------------------------------- #
    def _tally(upto: int) -> dict[str, DriverState]:
        pts: dict[str, float] = {}
        wins: dict[str, int] = {}
        stage_wins: dict[str, int] = {}
        bank: dict[str, float] = {}
        for r in rounds:
            if r > upto:
                continue
            t = per_round[r]
            for c, p in t["points"].items():
                pts[c] = pts.get(c, 0.0) + p
            if t["winner"]:
                wins[t["winner"]] = wins.get(t["winner"], 0) + 1
            for c in t["stage_winners"]:
                stage_wins[c] = stage_wins.get(c, 0) + 1
            for c, p in t["playoff_points"].items():
                bank[c] = bank.get(c, 0.0) + p
        return {
            c: DriverState(
                points=pts.get(c, 0.0),
                wins=wins.get(c, 0),
                stage_wins=stage_wins.get(c, 0),
                playoff_points=bank.get(c, 0.0),
            )
            for c in pts
        }

    if through <= reg or len(reg_rounds) < reg:
        drivers = _tally(through)
        return SeasonState(drivers=drivers), reg - len(reg_rounds)

    # --- regular season complete: award the top-10 playoff-point bonus ----- #
    reg_tallies = _tally(reg)
    reg_order = sorted(
        reg_tallies, key=lambda c: (reg_tallies[c].points, reg_tallies[c].wins), reverse=True
    )
    bonus: dict[str, float] = {}
    for pos, c in enumerate(reg_order, start=1):
        if pos in fmt.regular_season_playoff_points:
            bonus[c] = float(fmt.regular_season_playoff_points[pos])

    full = _tally(through)
    drivers = {
        c: DriverState(
            points=st.points,
            wins=st.wins,
            stage_wins=st.stage_wins,
            playoff_points=st.playoff_points + bonus.get(c, 0.0),
        )
        for c, st in full.items()
    }
    if through == reg:
        return SeasonState(drivers=drivers), 0

    # --- reconstruct the playoff walk over actual results ------------------ #
    qual_tallies = {
        c: DriverState(
            points=st.points,
            wins=st.wins,
            stage_wins=st.stage_wins,
            playoff_points=st.playoff_points + bonus.get(c, 0.0),
        )
        for c, st in reg_tallies.items()
    }
    seed_order = _qualification_order(qual_tallies, fmt)[: fmt.playoff_field_size]
    alive: list[str] = list(seed_order)
    bank = {c: qual_tallies[c].playoff_points if c in qual_tallies else 0.0 for c in alive}

    race_no = reg
    for r_idx, rnd_def in enumerate(fmt.rounds):
        # Round start: points reset (+ seed bonus + bank).
        rp: dict[str, float] = {}
        for seed_pos, c in enumerate(seed_order):
            if c not in alive:
                continue
            base = float(rnd_def.base_points or 0.0)
            if rnd_def.seed_bonus and seed_pos < len(rnd_def.seed_bonus):
                base += float(rnd_def.seed_bonus[seed_pos])
            if rnd_def.bank_playoff_points:
                base += bank.get(c, 0.0)
            rp[c] = base
        round_wins: dict[str, int] = {}

        for i in range(rnd_def.n_races):
            race_no += 1
            if race_no > through:
                return (
                    SeasonState(
                        drivers=drivers,
                        playoff=PlayoffPhaseState(
                            round_index=r_idx,
                            races_completed_in_round=i,
                            alive=tuple(alive),
                            round_points=rp,
                            round_wins=round_wins,
                        ),
                    ),
                    0,
                )
            t = per_round.get(race_no)
            if t is None:
                continue  # a missing playoff round in the data — skip honestly
            for c in alive:
                rp[c] = rp.get(c, 0.0) + t["points"].get(c, 0.0)
            w = t["winner"]
            if w in alive:
                round_wins[w] = round_wins.get(w, 0) + 1
            # Bank playoff points as actually earned (feed rows are exact:
            # 5 per win + 1 per stage win; pre-2020 they were reconstructed
            # above from the same constants).
            for c, p in t["playoff_points"].items():
                if c in alive:
                    bank[c] = bank.get(c, 0.0) + p

        if rnd_def.advancing is not None:
            cut = sorted(
                alive,
                key=lambda c: (
                    1 if (rnd_def.win_advances and round_wins.get(c)) else 0,
                    rp.get(c, 0.0),
                ),
                reverse=True,
            )[: rnd_def.advancing]
            seed_order = cut
            alive = list(cut)

    # Season fully complete — no playoff phase left to simulate.
    return SeasonState(drivers=drivers), 0


# --------------------------------------------------------------------------- #
# Championship: title odds through the REAL playoff format
# --------------------------------------------------------------------------- #
def playoff_projection(
    source: NascarDataSource,
    year: int = 0,
    *,
    fmt: PlayoffFormat | None = None,
    through_round: int | None = None,
    n_sims: int = 2000,
    rng_seed: int = 42,
) -> dict[str, dict[str, float]]:
    """Per-driver playoff probability ladder for the season.

    Routes through :func:`championship_playoffs.project_playoffs` with the
    format actually in force (:data:`config.CUP_CURRENT_FORMAT` unless
    overridden — the playoff backtest passes the 2017-2025 elimination
    format). Strengths come from the leakage-safe skill estimate at the next
    round; drivers who scored earlier but are absent from the current entry
    picture get back-of-field pace so the season state stays complete.
    """
    year = year or config.SEASON
    fmt = fmt or config.CUP_CURRENT_FORMAT
    completed = source.completed_rounds(year)
    through = through_round if through_round is not None else (
        max(completed) if completed else 0
    )
    state, remaining_reg = build_season_state(source, year, fmt, through_round=through)

    strengths = model.estimate_skill(source, year, through + 1)
    # The engine samples the FULL field: every tallied driver must have a
    # strength. Part-timers outside the entry picture get back-of-field pace.
    worst = max(strengths.values()) if strengths else config.PACE_BASE
    for c in state.drivers:
        strengths.setdefault(c, worst + 0.5)

    # Two championship-horizon uncertainty layers (both tuned on the playoff
    # backtest — see config.py):
    #  * a higher Plackett-Luce temperature than a single-race forecast;
    #  * skill-estimate uncertainty — average the ladder over batches with
    #    independently jittered strength vectors, so "who is actually
    #    fastest" varies across simulations instead of compounding one point
    #    estimate over 10-27 races.
    import numpy as np

    sigma = float(config.SKILL_UNCERTAINTY_SIGMA)
    batches = max(1, int(config.SKILL_UNCERTAINTY_BATCHES)) if sigma > 0 else 1
    codes = list(strengths.keys())
    rng = np.random.default_rng(rng_seed)
    sims_per_batch = max(200, n_sims // batches)

    acc: dict[str, dict[str, float]] = {}
    for b in range(batches):
        if sigma > 0 and batches > 1:
            jitter = rng.normal(0.0, sigma, size=len(codes))
            batch_strengths = {c: strengths[c] + float(jitter[i]) for i, c in enumerate(codes)}
        else:
            batch_strengths = dict(strengths)
        ladder = _project_playoffs(
            batch_strengths,
            fmt,
            completed_results=state,
            remaining_schedule=remaining_reg,
            n_sims=sims_per_batch,
            rng_seed=rng_seed + b,
            temperature=config.CHAMPIONSHIP_TEMPERATURE,
        )
        for c, probs in ladder.items():
            slot = acc.setdefault(c, {k: 0.0 for k in probs})
            for k, v in probs.items():
                slot[k] = slot.get(k, 0.0) + v
    return {
        c: {k: v / batches for k, v in probs.items()} for c, probs in acc.items()
    }


def project_title(
    source: NascarDataSource, year: int = 0, *, n_samples: int | None = None
) -> list[championship.TitleProjection]:
    """Family-shaped championship list: ``p_title`` from the playoff engine,
    points projection to the end of the regular season (Chase resets make a
    cross-boundary points projection meaningless)."""
    year = year or config.SEASON
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    current_points = current_driver_points(source, year)
    skill = model.estimate_skill(source, year, n_completed + 1)
    for c in current_points:
        skill.setdefault(c, max(skill.values(), default=config.PACE_BASE) + 0.5)

    remaining_reg = max(0, config.REGULAR_SEASON_RACES - n_completed)
    proj = model.project_regular_season_points(
        current_points, skill, remaining_reg, n_samples=n_samples
    )
    ladder = playoff_projection(source, year)
    by_key = {t.key: t for t in proj}
    out: list[championship.TitleProjection] = []
    for code, probs in ladder.items():
        base = by_key.get(code)
        out.append(
            championship.TitleProjection(
                key=code,
                p_title=float(probs.get("p_title", 0.0)),
                current_points=float(current_points.get(code, 0.0)),
                proj_mean=base.proj_mean if base else float(current_points.get(code, 0.0)),
                proj_p10=base.proj_p10 if base else float(current_points.get(code, 0.0)),
                proj_p90=base.proj_p90 if base else float(current_points.get(code, 0.0)),
            )
        )
    out.sort(key=lambda t: (-t.p_title, -t.current_points))
    return out


# --------------------------------------------------------------------------- #
# Skill + per-round forecast (delegated to the Cup model)
# --------------------------------------------------------------------------- #
def estimate_pace(source: NascarDataSource, year: int, current_round: int) -> dict[str, float]:
    """Per-driver pace (lower = faster) from rounds STRICTLY BEFORE
    ``current_round`` (plus the era-windowed prior-season Elo seed)."""
    return model.estimate_skill(source, year, current_round)


def forecast_round(
    source: NascarDataSource,
    year: int,
    round: int,
    *,
    n_samples: int | None = None,
    known_grid: list[str] | None = None,
) -> model.RoundForecastNascar:
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
    source: NascarDataSource, year: int, round: int, *, n_samples: int | None = None
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
