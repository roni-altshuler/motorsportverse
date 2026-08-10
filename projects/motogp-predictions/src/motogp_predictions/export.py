"""Generate the MotoGP website's JSON data from the model + committed snapshot.

The website is a static export: it reads everything from ``public/data/`` at build
time, so this module is the single producer of that contract. It mirrors the F3
golden template's fan-out shape (which itself mirrors the F1 flagship) so the two
sites can share components 1:1 — adapted to MotoGP terms: riders instead of
drivers, manufacturers instead of teams, and two shared-grid races per round
(Saturday **Sprint** = race_index 0, Sunday **Grand Prix** / "feature" = 1).

    public/data/
      motogp.json                 season summary (calendar, rider + manufacturer
                                  standings, championship, next-round prediction,
                                  season accuracy)
      rounds/round_NN.json        per-round sprint + GP classification, grid, and
                                  (for completed rounds) actual results + accuracy
      probabilities/round_NN.json per-race market probabilities + H2H + calibration
      calibration_summary.json    honest calibration status (real corpus → applied)
      seasons.json                multi-season index (current + archives)

The continuous-learning files (forward_eval/, model_health.json) are written by
the sibling :mod:`motogp_predictions.forward_eval` CLI, which needs real actuals.

Every forecast is leakage-safe (each round's pace uses only prior rounds) and,
where a real qualifying grid is published, conditioned on that grid — the
**post-quali** production surface validated to beat the raw-grid baseline
(``config.GRID_WEIGHT``). Conditioning on a round's own qualifying is not leakage:
qualifying runs before the race and is an input, never the label.

Run:  python -m motogp_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval, standings

from . import config, model
from .datasource import MotoGPDataSource
from .model import RaceForecast, RoundForecast

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# Single source of truth for manufacturer colours — straight from config.
TEAM_COLOR: dict[str, str] = {t.name: t.color for t in config.TEAMS}
_NEUTRAL = "#8A8A8A"

# Per-race H2H is only useful for the contenders; cap it so files stay small.
H2H_TOP_N = 12

# Grand Prix (25) + Sprint (12); MotoGP has no pole/fastest-lap championship points.
_MAX_POINTS_PER_ROUND = max(config.SPRINT_POINTS.values()) + max(config.FEATURE_POINTS.values())


def out_dir_for_season(year: int, base: Path = DEFAULT_OUT) -> Path:
    """Data root for a season's website files: the ACTIVE season at the top level,
    ARCHIVED seasons under ``seasons/<year>/`` (mirrors the F1/F3 multi-season layout)."""
    return base if int(year) == int(config.SEASON) else base / "seasons" / str(year)


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _headshot(code: str) -> str:
    return f"/headshots/{code}.webp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _color(team: str) -> str:
    return TEAM_COLOR.get(team, _NEUTRAL)


def _actual_map(source: MotoGPDataSource, year: int, rnd: int, race_type: str) -> dict[str, int]:
    results = source.race_results_for_round(year, rnd)[race_type]
    return {r.competitor: r.position for r in results if r.position is not None}


def _real_completed_rounds(source: MotoGPDataSource, year: int) -> list[int]:
    """Completed rounds backed by real results. MotoGP has no synthetic source —
    every completed round in the committed snapshot is real — so this is simply the
    completed rounds that carry a classified Grand Prix, provenance-agnostic."""
    return [
        r
        for r in range(1, config.COMPLETED_ROUNDS + 1)
        if source.race_results_for_round(year, r)["feature"]
    ]


def _next_round(source: MotoGPDataSource, year: int) -> int | None:
    """The upcoming round (first not-yet-completed), or None if the season is over."""
    completed = source.completed_rounds(year)
    nxt = (max(completed) + 1) if completed else 1
    return nxt if nxt <= len(config.CALENDAR) else None


def _known_grid(source: MotoGPDataSource, year: int, rnd: int) -> list[str] | None:
    """Real qualifying order (P1 first) for a round, or None when not yet published."""
    return source.qualifying(year, rnd)


# --------------------------------------------------------------------------- #
# Per-round detail (rounds/round_NN.json)
# --------------------------------------------------------------------------- #
def _classification(race: RaceForecast, actual: dict[str, int]) -> list[dict]:
    m = race.markets
    rows: list[dict] = []
    for pos, code in enumerate(race.order, start=1):
        team = config.TEAM_OF.get(code, "")
        rows.append(
            {
                "position": pos,
                "code": code,
                "name": config.DRIVER_NAME.get(code, code),
                "number": config.RIDER_NUMBER.get(code),
                "nationality": config.RIDER_NATION.get(code),
                "team": team,
                "teamColor": _color(team),
                "predictedValue": round(race.score[code], 3),
                "pWin": round(m.p_win.get(code, 0.0), 4),
                "pPodium": round(m.p_podium.get(code, 0.0), 4),
                "pTop6": round(m.p_top6.get(code, 0.0), 4),
                "pTop10": round(m.p_top10.get(code, 0.0), 4),
                "meanFinish": round(race.mean_finish[code], 2),
                "finishRangeLow": race.range_low[code],
                "finishRangeHigh": race.range_high[code],
                "confidence": race.confidence.get(code, "Medium"),
                "headshotUrl": _headshot(code),
                "actualPosition": actual.get(code),
            }
        )
    return rows


def _grid(race: RaceForecast) -> list[dict]:
    return [
        {
            "position": i,
            "code": code,
            "name": config.DRIVER_NAME.get(code, code),
            "team": config.TEAM_OF.get(code, ""),
        }
        for i, code in enumerate(race.grid, start=1)
    ]


def _race_block(
    race: RaceForecast, source: MotoGPDataSource, year: int, rnd: int, completed: bool
) -> dict:
    actual = _actual_map(source, year, rnd, race.race_type) if completed else {}
    block: dict = {
        "raceType": race.race_type,
        "grid": _grid(race),
        "classification": _classification(race, actual),
    }
    if completed and actual:
        block["actualResults"] = [
            {"position": pos, "code": code}
            for code, pos in sorted(actual.items(), key=lambda kv: kv[1])
        ]
        predicted = {code: i for i, code in enumerate(race.order, start=1)}
        block["accuracy"] = core_eval.score_round(predicted, actual)
    return block


def _model_config(known_grid: list[str] | None) -> dict:
    """A/B lever provenance for the round — mirrors F1/F3's ``modelConfig`` block.

    MotoGP's real production lever is **grid conditioning**: once the round's real
    qualifying is published the forecast is conditioned on the actual grid (the
    validated post-quali surface); pre-quali it uses the predicted merit grid.
    MotoGP carries no direct finishing-position head (unlike F3's opt-in one), so
    ``positionModel.applied`` is honestly always ``false`` — kept for 1:1 shape.
    """
    return {
        "gridProvenance": "real-quali" if known_grid else "estimated",
        "positionModel": {"applied": False},
    }


def round_payload(
    fc: RoundForecast, source: MotoGPDataSource, completed: bool, known_grid: list[str] | None
) -> dict:
    data_source = source.provenance(fc.season, fc.round, race_index=1) if completed else None
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "country": fc.country,
        "completed": completed,
        "dataSource": data_source,  # real provenance ("snapshot") for completed rounds
        "modelConfig": _model_config(known_grid),
        "sprint": _race_block(fc.sprint, source, fc.season, fc.round, completed),
        "feature": _race_block(fc.feature, source, fc.season, fc.round, completed),
    }


# --------------------------------------------------------------------------- #
# Per-round probabilities (probabilities/round_NN.json)
# --------------------------------------------------------------------------- #
def _h2h_subset(race: RaceForecast) -> dict[str, dict[str, float]]:
    """Head-to-head matrix restricted to the round's top contenders."""
    top = list(race.order[:H2H_TOP_N])
    h2h = race.markets.h2h
    return {
        a: {b: round(h2h[a][b], 4) for b in top if b in h2h.get(a, {})}
        for a in top
        if a in h2h
    }


_RAW_MARKET_KEYS = ("win", "podium", "top6", "top10")


def _calibrate_markets(race: RaceForecast, calibrator) -> dict:
    """Per-market probabilities, calibrated per race-type stratum when fitted.

    Falls back to the raw Monte-Carlo probability when the (market, stratum) has no
    fitted model — so the output is always honest about what was calibrated."""
    raw_by_market = {
        "win": race.markets.p_win,
        "podium": race.markets.p_podium,
        "top6": race.markets.p_top6,
        "top10": race.markets.p_top10,
    }
    out: dict[str, dict[str, dict[str, float]]] = {}
    for market in _RAW_MARKET_KEYS:
        raw = raw_by_market[market]
        codes = list(raw.keys())
        raw_vals = np.array([raw[c] for c in codes], dtype=float)
        if calibrator is not None and calibrator.is_fitted(market, race.race_type):
            cal_vals = calibrator.transform(market, raw_vals, stratum=race.race_type)
        else:
            cal_vals = raw_vals
        # The win market is mutually exclusive — exactly one winner — so its
        # calibrated probabilities must sum to 1.0. Per-market isotonic calibration
        # + the probability floor over MotoGP's ~29-rider field inflates the sum
        # (1.2-1.5), so renormalise win to a coherent market (order + the
        # anti-collapse floor are preserved; the top probability only shrinks).
        # The top-k markets (podium/top6/top10) are independent per-rider
        # probabilities that legitimately sum to k, so they are left as-is.
        if market == "win":
            total = float(cal_vals.sum())
            if total > 0:
                cal_vals = cal_vals / total
        out[market] = {
            c: {
                "probability": round(float(cal_vals[i]), 4),
                "rawProbability": round(float(raw_vals[i]), 4),
            }
            for i, c in enumerate(codes)
        }
    return out


def _race_probabilities(race: RaceForecast, calibrator) -> dict:
    return {
        "raceType": race.race_type,
        "markets": _calibrate_markets(race, calibrator),
        "h2h": _h2h_subset(race),
        "method": "monte-carlo",
        "monteCarloSamples": race.n_samples,
        "temperature": race.temperature,
    }


def probabilities_payload(fc: RoundForecast, calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    reason = (
        f"calibrated on {real_rounds} real round(s) of results"
        if applied
        else f"awaiting {config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds "
        f"({real_rounds} so far); showing raw Monte-Carlo probabilities"
    )
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "calibration": {"applied": applied, "reason": reason},
        "sprint": _race_probabilities(fc.sprint, calibrator),
        "feature": _race_probabilities(fc.feature, calibrator),
    }


def build_calibrator(round_forecasts: dict[int, RoundForecast], source: MotoGPDataSource, year: int):
    """Fit a per-race-type probability calibrator from the *real* completed rounds.

    Reuses the leakage-safe post-quali forecasts already computed (each conditioned
    on that round's real grid). Below ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it
    returns ``(None, count)`` so the site honestly reports calibration as not-yet-
    applied — the shared F1/F3 gate. MotoGP ships a full real corpus, so it fits."""
    real_rounds = _real_completed_rounds(source, year)
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)

    records: list[dict] = []
    for rnd in real_rounds:
        fc = round_forecasts[rnd]
        for race, race_type in ((fc.feature, model.FEATURE), (fc.sprint, model.SPRINT)):
            actual = _actual_map(source, year, rnd, race_type)
            recs = calibration.collect_history_from_rounds({rnd: race.markets}, {rnd: actual})
            for rec in recs:
                rec["stratum"] = race_type
            records.extend(recs)

    calibrator = calibration.StratifiedProbabilityCalibrator().fit_from_history(records)
    return (calibrator if calibrator.is_fitted() else None), len(real_rounds)


def _calibration_summary(calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    per_market = {m: 0 for m in calibration.MARKETS}
    if applied:
        counts = calibrator.sample_counts().get("global", {})
        if isinstance(counts, dict):
            per_market.update({m: int(counts.get(m, 0)) for m in calibration.MARKETS})
    return {
        "generatedAt": _now_iso(),
        "applied": applied,
        "trainingRounds": real_rounds,
        "dataLimitation": (
            "Calibrated on real MotoGP results (Sprint + Grand Prix, per race-type stratum)."
            if applied
            else "Probability calibration turns on once "
            f"{config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds accrue "
            f"({real_rounds} so far)."
        ),
        "perMarket": per_market,
    }


# --------------------------------------------------------------------------- #
# Standings (rider + manufacturer), replayed from real results
# --------------------------------------------------------------------------- #
def _replay_standings(source: MotoGPDataSource, year: int):
    """Cumulative rider- and manufacturer-points after each completed round, plus
    final wins/podiums. Sprint + Grand Prix points are both counted."""
    codes = [d["code"] for d in config.DRIVERS]
    manus = list(dict.fromkeys(config.TEAM_OF.values()))
    driver_hist: dict[str, list[float]] = {c: [] for c in codes}
    team_hist: dict[str, list[float]] = {m: [] for m in manus}

    sprints: list[dict[str, int]] = []
    features: list[dict[str, int]] = []
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        races = source.race_results_for_round(year, rnd)
        sprints.append({r.competitor: r.position for r in races["sprint"]})
        features.append({r.competitor: r.position for r in races["feature"]})

        d_merged = standings.merge_standings(
            standings.compute_driver_standings(sprints, config.SPRINT_POINTS),
            standings.compute_driver_standings(features, config.FEATURE_POINTS),
        )
        d_points = {row.key: row.points for row in d_merged}
        for c in codes:
            driver_hist[c].append(d_points.get(c, 0))

        t_merged = standings.merge_standings(
            standings.compute_team_standings(sprints, config.SPRINT_POINTS, config.TEAM_OF),
            standings.compute_team_standings(features, config.FEATURE_POINTS, config.TEAM_OF),
        )
        t_points = {row.key: row.points for row in t_merged}
        for m in manus:
            team_hist[m].append(t_points.get(m, 0))

    d_final = standings.merge_standings(
        standings.compute_driver_standings(sprints, config.SPRINT_POINTS),
        standings.compute_driver_standings(features, config.FEATURE_POINTS),
    )
    t_final = standings.merge_standings(
        standings.compute_team_standings(sprints, config.SPRINT_POINTS, config.TEAM_OF),
        standings.compute_team_standings(features, config.FEATURE_POINTS, config.TEAM_OF),
    )
    driver_wp = {r.key: (r.wins, r.podiums, r.points) for r in d_final}
    team_wp = {r.key: (r.wins, r.podiums, r.points) for r in t_final}
    return driver_hist, team_hist, driver_wp, team_wp


def _standings_lists(source: MotoGPDataSource, year: int) -> tuple[list[dict], list[dict]]:
    """(riderStandings, manufacturerStandings). Uses the snapshot's **official**
    point totals for display (exact), and replays results for wins/podiums and the
    per-round cumulative history the progression chart draws."""
    driver_hist, team_hist, driver_wp, team_wp = _replay_standings(source, year)
    snap = config.load_snapshot(year)
    official_drivers = snap.get("driverStandings") if snap.get("season") == year else None
    official_teams = snap.get("teamStandings") if snap.get("season") == year else None

    # Riders.
    driver_rows: list[dict] = []
    if official_drivers:
        for i, d in enumerate(official_drivers, start=1):
            code = d["code"]
            team = config.TEAM_OF.get(code, d.get("manufacturer", ""))
            wins, podiums, _pts = driver_wp.get(code, (0, 0, 0.0))
            driver_rows.append(
                {
                    "position": i,
                    "code": code,
                    "name": config.DRIVER_NAME.get(code, d.get("name", code)),
                    "number": config.RIDER_NUMBER.get(code),
                    "nationality": config.RIDER_NATION.get(code),
                    "team": team,
                    "teamColor": _color(team),
                    "points": float(d["points"]),
                    "wins": wins,
                    "podiums": podiums,
                    "pointsHistory": driver_hist.get(code, []),
                }
            )
    else:  # fallback: recompute entirely from results
        ranked = sorted(driver_wp.items(), key=lambda kv: -kv[1][2])
        for i, (code, (wins, podiums, pts)) in enumerate(ranked, start=1):
            team = config.TEAM_OF.get(code, "")
            driver_rows.append(
                {
                    "position": i,
                    "code": code,
                    "name": config.DRIVER_NAME.get(code, code),
                    "number": config.RIDER_NUMBER.get(code),
                    "nationality": config.RIDER_NATION.get(code),
                    "team": team,
                    "teamColor": _color(team),
                    "points": float(pts),
                    "wins": wins,
                    "podiums": podiums,
                    "pointsHistory": driver_hist.get(code, []),
                }
            )

    # Manufacturers.
    team_rows: list[dict] = []
    if official_teams:
        for i, t in enumerate(official_teams, start=1):
            name = t["name"]
            wins, podiums, _pts = team_wp.get(name, (0, 0, 0.0))
            team_rows.append(
                {
                    "position": i,
                    "team": name,
                    "teamColor": _color(name),
                    "points": float(t["points"]),
                    "wins": wins,
                    "podiums": podiums,
                    "pointsHistory": team_hist.get(name, []),
                }
            )
    else:
        ranked = sorted(team_wp.items(), key=lambda kv: -kv[1][2])
        for i, (name, (wins, podiums, pts)) in enumerate(ranked, start=1):
            team_rows.append(
                {
                    "position": i,
                    "team": name,
                    "teamColor": _color(name),
                    "points": float(pts),
                    "wins": wins,
                    "podiums": podiums,
                    "pointsHistory": team_hist.get(name, []),
                }
            )
    return driver_rows, team_rows


def _current_points(driver_rows: list[dict]) -> dict[str, float]:
    return {d["code"]: float(d["points"]) for d in driver_rows}


# --------------------------------------------------------------------------- #
# Championship (rider title, can-still-win math)
# --------------------------------------------------------------------------- #
def _championship(source: MotoGPDataSource, year: int, current_points: dict[str, float]) -> list[dict]:
    skill = model.estimate_skill(source, year, current_round=config.COMPLETED_ROUNDS + 1)
    remaining = config.TOTAL_ROUNDS - config.COMPLETED_ROUNDS
    # Seed with the full real roster's current points (0 for the winless).
    points = {c: float(current_points.get(c, 0.0)) for c in skill}
    title = model.project_championship_motogp(points, skill, remaining_rounds=remaining)
    leader_points = max((t.current_points for t in title), default=0.0)
    ceiling = max(remaining, 0) * _MAX_POINTS_PER_ROUND
    out: list[dict] = []
    for t in title:
        max_attainable = t.current_points + ceiling
        out.append(
            {
                "code": t.key,
                "name": config.DRIVER_NAME.get(t.key, t.key),
                "team": config.TEAM_OF.get(t.key, ""),
                "pTitle": round(t.p_title, 4),
                "currentPoints": t.current_points,
                "projMean": round(t.proj_mean, 3),
                "projP10": t.proj_p10,
                "projP90": t.proj_p90,
                "maxAttainable": max_attainable,
                "canStillWin": max_attainable >= leader_points,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Season accuracy (Grand Prix, leakage-safe per-round predictions vs actual)
# --------------------------------------------------------------------------- #
def _season_accuracy(
    round_forecasts: dict[int, RoundForecast], source: MotoGPDataSource, year: int
) -> dict:
    scored = 0
    pos_errors: list[float] = []
    podium_hits = 0
    winner_hits = 0
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        fc = round_forecasts[rnd]
        actual = _actual_map(source, year, rnd, model.FEATURE)
        if not actual:
            continue
        predicted = {code: i for i, code in enumerate(fc.feature.order, start=1)}
        score = core_eval.score_round(predicted, actual)
        if score.get("n", 0) == 0:
            continue
        scored += 1
        if score.get("mean_position_error") is not None:
            pos_errors.append(score["mean_position_error"])
        podium_hits += score.get("podium_hits", 0)
        winner_hits += 1 if score.get("winner_hit") else 0
    return {
        "roundsScored": scored,
        "meanPositionError": round(sum(pos_errors) / len(pos_errors), 3) if pos_errors else None,
        "podiumHitRate": round(podium_hits / (scored * 3), 4) if scored else None,
        "winnerHitRate": round(winner_hits / scored, 4) if scored else None,
    }


# --------------------------------------------------------------------------- #
# Multi-season index
# --------------------------------------------------------------------------- #
def write_seasons_index(out_dir: Path = DEFAULT_OUT, current: int | None = None) -> dict:
    """Write ``seasons.json`` — the multi-season index the website reads. Archived
    years are discovered by scanning ``<out_dir>/seasons/`` (same schema as F1/F3)."""
    cur = int(current if current is not None else config.SEASON)
    seasons_dir = out_dir / "seasons"
    archived = sorted(
        int(p.name)
        for p in (seasons_dir.iterdir() if seasons_dir.is_dir() else [])
        if p.is_dir() and p.name.isdigit() and int(p.name) != cur
    )
    available = sorted(set(archived) | {cur})
    index = {
        "current": cur,
        "available": available,
        "archived": archived,
        "lastUpdated": _now_iso(),
        "seasons": [
            {
                "year": y,
                "isCurrent": y == cur,
                "path": "" if y == cur else f"seasons/{y}",
                "label": str(y),
            }
            for y in available
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seasons.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


# --------------------------------------------------------------------------- #
# Top-level season summary (motogp.json)
# --------------------------------------------------------------------------- #
def build_payload(
    round_forecasts: dict[int, RoundForecast],
    source: MotoGPDataSource,
    year: int,
    next_round: int | None,
) -> dict:
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    driver_rows, team_rows = _standings_lists(source, year)
    current_points = _current_points(driver_rows)

    prediction = None
    if next_round is not None:
        fc = round_forecasts[next_round]
        feature = fc.feature
        post_quali = _known_grid(source, year, next_round) is not None
        prediction = {
            "season": fc.season,
            "round": fc.round,
            "venueKey": fc.venue_key,
            "venueName": fc.venue_name,
            "phase": "post-quali" if post_quali else "pre",
            "qualifyingActual": post_quali,
            "qualifying": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME.get(c, c),
                    "team": config.TEAM_OF.get(c, ""),
                }
                for i, c in enumerate(feature.grid, start=1)
            ],
            "race": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME.get(c, c),
                    "team": config.TEAM_OF.get(c, ""),
                    "pWin": round(feature.markets.p_win.get(c, 0.0), 4),
                    "pPodium": round(feature.markets.p_podium.get(c, 0.0), 4),
                }
                for i, c in enumerate(feature.order, start=1)
            ],
        }

    meta = config.CALENDAR_META
    return {
        "sport": config.SPORT,
        "season": year,
        "generatedAt": _now_iso(),
        "completedRounds": n_completed,
        "lastUpdatedRound": max(completed) if completed else 0,
        "totalRounds": config.TOTAL_ROUNDS,
        "calendar": [
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "city": meta.get(i, {}).get("city", ""),
                "event": meta.get(i, {}).get("event", ""),
                "date": meta.get(i, {}).get("date", ""),
                "completed": i in completed,
                "dataSource": source.provenance(year, i, race_index=1) if i in completed else None,
            }
            for i, v in enumerate(config.CALENDAR, start=1)
        ],
        "driverStandings": driver_rows,
        "teamStandings": team_rows,
        "championship": _championship(source, year, current_points),
        "seasonAccuracy": _season_accuracy(round_forecasts, source, year),
        "nextPrediction": prediction,
    }


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rounds_dir = out_dir / "rounds"
    probs_dir = out_dir / "probabilities"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    probs_dir.mkdir(parents=True, exist_ok=True)

    source = MotoGPDataSource()
    year = config.SEASON
    next_round = _next_round(source, year)

    # Forecast every round once, leakage-safe. Each round is conditioned on its own
    # real qualifying grid when published (the post-quali production surface) — that
    # is an input, not a leak; the pace still uses only strictly-prior rounds.
    round_forecasts: dict[int, RoundForecast] = {}
    grids: dict[int, list[str] | None] = {}
    for rnd in range(1, len(config.CALENDAR) + 1):
        known_grid = _known_grid(source, year, rnd)
        grids[rnd] = known_grid
        fc = model.forecast_round(source, year, rnd, known_grid=known_grid)
        round_forecasts[rnd] = fc

    # Honest calibration gate (fit from the real completed rounds' post-quali markets).
    calibrator, real_rounds = build_calibrator(round_forecasts, source, year)

    for rnd, fc in round_forecasts.items():
        completed = rnd <= config.COMPLETED_ROUNDS
        (rounds_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(round_payload(fc, source, completed, grids[rnd]), indent=2) + "\n"
        )
        (probs_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(probabilities_payload(fc, calibrator, real_rounds), indent=2) + "\n"
        )

    (out_dir / "calibration_summary.json").write_text(
        json.dumps(_calibration_summary(calibrator, real_rounds), indent=2) + "\n"
    )

    payload = build_payload(round_forecasts, source, year, next_round)
    path = out_dir / "motogp.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")

    write_seasons_index(out_dir, current=year)
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    path = write(args.out)
    print(f"Wrote {path} and per-round files under {path.parent}/rounds and /probabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
