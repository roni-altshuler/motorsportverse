"""Generate the NASCAR website's JSON data from the model + pipeline.

The website is a static export: it reads everything from ``public/data/`` at
build time, so this module is the single producer of that contract. It mirrors
the F1/F2/F3/FE fan-out shape so the NASCAR site reuses the family's
components 1:1, plus the NASCAR-specific playoff projection:

    public/data/
      nascar.json                 season summary (calendar, standings,
                                  championship, next-round prediction,
                                  season accuracy)
      rounds/round_NN.json        per-round race classification, grid, stage
                                  results and (for completed rounds) actual
                                  results + accuracy
      probabilities/round_NN.json per-race market probabilities + H2H +
                                  calibration state (track-type strata)
      playoff_projection.json     per-driver playoff ladder through the REAL
                                  2026 Chase format (p_make_playoffs, p_title)
      calibration_summary.json    honest calibration status
      seasons.json                multi-season index (current + archives)

The continuous-learning files (forward_eval/, model_health.json,
promotion_status.json, historical_backtest/ incl. playoffs.json,
reliability_plots/) are written by the sibling CLIs.

Run:  python -m nascar_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, pipeline
from .datasource import NascarDataSource
from .model import RaceForecast, RoundForecastNascar
from .sources.composite import CompositeNascarSource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"


def out_dir_for_season(year: int, base: Path = DEFAULT_OUT) -> Path:
    """Data root for a season's website files.

    The ACTIVE season lives at the top level of ``website/public/data`` (so
    the current-season contract never moves); ARCHIVED seasons live under
    ``seasons/<year>/`` (created by ``season_rollover.py``).
    """
    return base if int(year) == int(config.SEASON) else base / "seasons" / str(year)


def write_seasons_index(out_dir: Path = DEFAULT_OUT, current: int | None = None) -> dict:
    """Write ``seasons.json`` — the multi-season index the website reads to
    know which seasons exist and which is current."""
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
                # base path the frontend appends after its data root
                "path": "" if y == cur else f"seasons/{y}",
                "label": config.season_label(y),
            }
            for y in available
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seasons.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


# Single source of truth for colours — straight from config, never duplicated.
TEAM_COLOR: dict[str, str] = {t.name: t.color for t in config.TEAMS}
_FALLBACK_COLOR = "#FFD659"  # NASCAR racing yellow

# Per-race H2H is only useful for the contenders; cap it so files stay small.
H2H_TOP_N = 12


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _headshot(code: str) -> str:
    return f"/headshots/{code}.webp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _actual_map(source: NascarDataSource, year: int, rnd: int) -> dict[str, int]:
    return {r.competitor: r.position for r in source.results(year, rnd)}


def _next_round(source: NascarDataSource, year: int) -> int | None:
    """The upcoming round number (the first not-yet-completed round), or None
    if the season is over. Feed-derived so it stays correct as rounds complete."""
    completed = source.completed_rounds(year)
    nxt = (max(completed) + 1) if completed else 1
    return nxt if nxt <= len(config.CALENDAR) else None


def _team_color(team: str) -> str:
    return TEAM_COLOR.get(team, _FALLBACK_COLOR)


# --------------------------------------------------------------------------- #
# Per-round detail (rounds/round_NN.json)
# --------------------------------------------------------------------------- #
def _classification(race: RaceForecast, source: NascarDataSource, actual: dict[str, int]) -> list[dict]:
    m = race.markets
    names = config.DRIVER_NAME
    rows: list[dict] = []
    for pos, code in enumerate(race.order, start=1):
        team = config.TEAM_OF.get(code, "")
        rows.append(
            {
                "position": pos,
                "code": code,
                "name": names.get(code, code),
                "team": team,
                "make": config.MAKE_OF.get(code, ""),
                "teamColor": _team_color(team),
                "predictedValue": round(race.score[code], 3),
                "pWin": round(m.p_win.get(code, 0.0), 4),
                "pPodium": round(m.p_podium.get(code, 0.0), 4),
                "pTop6": round(m.p_top6.get(code, 0.0), 4),
                "pTop10": round(m.p_top10.get(code, 0.0), 4),
                "pDnf": round(race.p_dnf.get(code, 0.0), 4),
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
    race: RaceForecast, source: NascarDataSource, year: int, rnd: int, completed: bool
) -> dict:
    actual = _actual_map(source, year, rnd) if completed else {}
    block: dict = {
        "raceType": race.race_type,
        "grid": _grid(race),
        "classification": _classification(race, source, actual),
    }
    if completed and actual:
        block["actualResults"] = [
            {"position": pos, "code": code}
            for code, pos in sorted(actual.items(), key=lambda kv: kv[1])
        ]
        rows = source.race_rows(year, rnd) or []
        status = {r["code"]: r.get("status", "Running") for r in rows}
        if status:
            block["actualStatus"] = status
        stages = source.stage_results(year, rnd)
        if stages:
            block["stageResults"] = {
                num: [
                    {"position": s["position"], "code": s["code"], "points": s["points"]}
                    for s in stage_rows
                ]
                for num, stage_rows in stages.items()
            }
        predicted = {code: i for i, code in enumerate(race.order, start=1)}
        block["accuracy"] = core_eval.score_round(predicted, actual)
    return block


def _model_config(fc: RoundForecastNascar) -> dict:
    """A/B lever provenance for the round — mirrors F1's ``modelConfig`` block."""
    head = fc.position_head
    position: dict = {"applied": bool(head.get("applied", False)) if head else False}
    if head:
        if head.get("trainedRounds") is not None:
            position["trainedRounds"] = [int(r) for r in head["trainedRounds"]]
        if head.get("trainRows") is not None:
            position["trainRows"] = int(head["trainRows"])
        if head.get("reason"):
            position["reason"] = str(head["reason"])
    return {"positionModel": position, "dnfComposition": {"applied": True}}


def round_payload(fc: RoundForecastNascar, source: NascarDataSource, completed: bool) -> dict:
    data_source = source.provenance(fc.season, fc.round) if completed else None
    meta = source.race_meta(fc.season, fc.round)
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "raceName": fc.race_name,
        "country": fc.country,
        "trackType": fc.track_type,
        "stageLaps": list(meta.get("stageLaps") or []),
        "raceDate": meta.get("date", ""),
        "completed": completed,
        "dataSource": data_source,  # "snapshot"/"nascar-feed" (real) or "synthetic"
        "modelConfig": _model_config(fc),
        "race": _race_block(fc.race, source, fc.season, fc.round, completed),
    }


# --------------------------------------------------------------------------- #
# Per-round probabilities (probabilities/round_NN.json)
# --------------------------------------------------------------------------- #
def _h2h_subset(race: RaceForecast) -> dict[str, dict[str, float]]:
    """Head-to-head matrix restricted to the round's top contenders."""
    top = [c for c in race.order[:H2H_TOP_N]]
    top_set = set(top)
    return {
        a: {b: round(race.markets.h2h[a][b], 4) for b in top if b in race.markets.h2h.get(a, {})}
        for a in top
        if a in race.markets.h2h
    } if top_set else {}


_RAW_MARKET_KEYS = ("win", "podium", "top6", "top10")


def _calibrate_markets(race: RaceForecast, calibrator, stratum: str) -> dict:
    """Per-market probabilities, calibrated per track-type stratum when fitted.

    NASCAR's calibration strata are the four track types — a superspeedway
    forecast and a road-course forecast have very different variance and the
    calibrator learns each honestly from real outcomes. Falls back to the raw
    Monte-Carlo probability when the (market, stratum) has no fitted model —
    always honest about what was calibrated.
    """
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
        if calibrator is not None and calibrator.is_fitted(market, stratum):
            cal_vals = calibrator.transform(market, raw_vals, stratum=stratum)
        else:
            cal_vals = raw_vals
        out[market] = {
            c: {
                "probability": round(float(cal_vals[i]), 4),
                "rawProbability": round(float(raw_vals[i]), 4),
            }
            for i, c in enumerate(codes)
        }
    return out


def _race_probabilities(fc: RoundForecastNascar, calibrator) -> dict:
    race = fc.race
    return {
        "raceType": race.race_type,
        "trackType": fc.track_type,
        "markets": _calibrate_markets(race, calibrator, fc.track_type),
        "dnf": {c: round(p, 4) for c, p in race.p_dnf.items()},
        "h2h": _h2h_subset(race),
        "method": "monte-carlo-dnf-composed",
        "monteCarloSamples": race.n_samples,
        "temperature": race.temperature,
    }


def probabilities_payload(fc: RoundForecastNascar, calibrator, real_rounds: int) -> dict:
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
        "race": _race_probabilities(fc, calibrator),
    }


def build_calibrator(source: NascarDataSource, year: int):
    """Fit a track-type-stratified probability calibrator from *real*
    completed rounds.

    Counts only rounds whose results came from a real feed (not synthetic).
    Below ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it returns
    ``(None, count)`` so the site honestly reports calibration as
    not-yet-applied.
    """
    real_rounds = [
        r
        for r in source.completed_rounds(year)
        if CompositeNascarSource.is_real(source.provenance(year, r))
    ]
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)

    records: list[dict] = []
    for rnd in real_rounds:
        fc = pipeline.forecast_round(source, year, rnd)
        actual = _actual_map(source, year, rnd)
        recs = calibration.collect_history_from_rounds({rnd: fc.race.markets}, {rnd: actual})
        for rec in recs:
            rec["stratum"] = fc.track_type
        records.extend(recs)

    calibrator = calibration.StratifiedProbabilityCalibrator().fit_from_history(records)
    return (calibrator if calibrator.is_fitted() else None), len(real_rounds)


# --------------------------------------------------------------------------- #
# Championship + playoff projection
# --------------------------------------------------------------------------- #
def _championship(source: NascarDataSource, year: int, ladder: dict) -> list[dict]:
    title = pipeline.project_title(source, year)
    leader_points = max((t.current_points for t in title), default=0.0)
    completed = len(source.completed_rounds(year))
    remaining_reg = max(0, config.REGULAR_SEASON_RACES - completed)
    max_per_round = max(config.RACE_POINTS_2026.values()) + config.STAGES_PER_RACE * max(
        config.STAGE_POINTS.values()
    )
    ceiling = remaining_reg * max_per_round
    out: list[dict] = []
    for t in title:
        probs = ladder.get(t.key, {})
        max_attainable = t.current_points + ceiling
        out.append(
            {
                "code": t.key,
                "name": config.DRIVER_NAME.get(t.key, t.key),
                "team": config.TEAM_OF.get(t.key, ""),
                "make": config.MAKE_OF.get(t.key, ""),
                "pTitle": round(t.p_title, 4),
                "pMakePlayoffs": round(float(probs.get("p_make_playoffs", 0.0)), 4),
                "currentPoints": t.current_points,
                # Projection horizon = end of the REGULAR season (the Chase
                # points reset makes a cross-boundary projection meaningless).
                "projMean": t.proj_mean,
                "projP10": t.proj_p10,
                "projP90": t.proj_p90,
                "projectionHorizon": "regular-season",
                "maxAttainable": max_attainable,
                # Points qualification: "can still win" = can still make the
                # top-16 points field (everyone in the field can win the Chase).
                "canStillWin": bool(probs.get("p_make_playoffs", 0.0) > 0.0)
                or max_attainable >= leader_points,
            }
        )
    return out


def playoff_projection_payload(source: NascarDataSource, year: int, ladder: dict) -> dict:
    fmt = config.CUP_CURRENT_FORMAT
    completed = source.completed_rounds(year)
    official = pipeline.official_standings(source, year) or {}
    by_code = {d["code"]: d for d in official.get("driverStandings", [])}
    drivers = []
    for code, probs in sorted(ladder.items(), key=lambda kv: -kv[1].get("p_title", 0.0)):
        d = by_code.get(code, {})
        drivers.append(
            {
                "code": code,
                "name": config.DRIVER_NAME.get(code, d.get("name", code)),
                "team": config.TEAM_OF.get(code, d.get("team", "")),
                "make": config.MAKE_OF.get(code, d.get("make", "")),
                "points": float(d.get("points", 0.0)),
                "wins": int(d.get("wins", 0)),
                "stageWins": int(d.get("stageWins", 0)),
                "ladder": {k: round(float(v), 4) for k, v in probs.items()},
                "pMakePlayoffs": round(float(probs.get("p_make_playoffs", 0.0)), 4),
                "pTitle": round(float(probs.get("p_title", 0.0)), 4),
            }
        )
    return {
        "season": year,
        "generatedAt": _now_iso(),
        "format": {
            "name": "chase-2026",
            "regularSeasonRaces": fmt.regular_season_races,
            "playoffRaces": sum(r.n_races for r in fmt.rounds),
            "playoffFieldSize": fmt.playoff_field_size,
            "qualification": fmt.qualification,
            "eliminations": any(r.advancing is not None for r in fmt.rounds),
            "probabilityKeys": list(fmt.probability_keys),
        },
        "completedRounds": len(completed),
        "regularSeasonRacesRemaining": max(0, fmt.regular_season_races - len(completed)),
        "method": "monte-carlo playoff simulation over the real 2026 Chase format",
        "drivers": drivers,
    }


# --------------------------------------------------------------------------- #
# Season accuracy (leakage-safe per-round predictions vs actual)
# --------------------------------------------------------------------------- #
def _season_accuracy(
    round_forecasts: dict[int, RoundForecastNascar], source: NascarDataSource, year: int
) -> dict:
    scored = 0
    pos_errors: list[float] = []
    podium_hits = 0
    winner_hits = 0
    for rnd in source.completed_rounds(year):
        fc = round_forecasts[rnd]
        actual = _actual_map(source, year, rnd)
        if not actual:
            continue
        predicted = {code: i for i, code in enumerate(fc.race.order, start=1)}
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
# Standings lists
# --------------------------------------------------------------------------- #
def _standings_lists(source: NascarDataSource, year: int) -> tuple[list[dict], list[dict], list[dict]]:
    """(driverStandings, teamStandings, manufacturerStandings) — official
    snapshot totals when the feed is real (exact, incl. stage points), else
    recomputed race-points-only fallback."""
    official = pipeline.official_standings(source, year)
    if official:
        driver_rows = [
            {
                "position": d["position"],
                "code": d["code"],
                "name": d.get("name", d["code"]),
                "team": d.get("team", ""),
                "make": d.get("make", ""),
                "teamColor": _team_color(d.get("team", "")),
                "points": d["points"],
                "wins": int(d.get("wins", 0)),
                "podiums": int(d.get("podiums", 0)),
                "top10s": int(d.get("top10s", 0)),
                "stageWins": int(d.get("stageWins", 0)),
                "lapsLed": int(d.get("lapsLed", 0)),
                "playoffPoints": float(d.get("playoffPoints", 0.0)),
                "pointsHistory": d.get("pointsHistory", []),
            }
            for d in official.get("driverStandings", [])
        ]
        team_rows = [
            {
                "position": t["position"],
                "team": t["team"],
                "teamColor": _team_color(t["team"]),
                "points": t["points"],
                "wins": int(t.get("wins", 0)),
                "podiums": int(t.get("podiums", 0)),
                "pointsHistory": t.get("pointsHistory", []),
            }
            for t in official.get("teamStandings", [])
        ]
        make_rows = [
            {
                "position": m["position"],
                "make": m["make"],
                "color": config.MANUFACTURER_COLORS.get(m["make"], _FALLBACK_COLOR),
                "points": m["points"],
                "wins": int(m.get("wins", 0)),
            }
            for m in official.get("manufacturerStandings", [])
        ]
        return driver_rows, team_rows, make_rows

    # Fallback: recompute from the source's results (synthetic / no snapshot).
    ds = pipeline.driver_standings(source, year)
    ts = pipeline.team_standings(source, year)
    ms = pipeline.manufacturer_standings(source, year)
    driver_rows = [
        {
            "position": i,
            "code": r.key,
            "name": config.DRIVER_NAME.get(r.key, r.key),
            "team": config.TEAM_OF.get(r.key, ""),
            "make": config.MAKE_OF.get(r.key, ""),
            "teamColor": _team_color(config.TEAM_OF.get(r.key, "")),
            "points": r.points,
            "wins": r.wins,
            "podiums": r.podiums,
            "top10s": 0,
            "stageWins": 0,
            "lapsLed": 0,
            "playoffPoints": 0.0,
            "pointsHistory": [],
        }
        for i, r in enumerate(ds, start=1)
    ]
    team_rows = [
        {
            "position": i,
            "team": r.key,
            "teamColor": _team_color(r.key),
            "points": r.points,
            "wins": r.wins,
            "podiums": r.podiums,
            "pointsHistory": [],
        }
        for i, r in enumerate(ts, start=1)
    ]
    make_rows = [
        {
            "position": i,
            "make": r.key,
            "color": config.MANUFACTURER_COLORS.get(r.key, _FALLBACK_COLOR),
            "points": r.points,
            "wins": r.wins,
        }
        for i, r in enumerate(ms, start=1)
    ]
    return driver_rows, team_rows, make_rows


# --------------------------------------------------------------------------- #
# Top-level builders
# --------------------------------------------------------------------------- #
def build_payload(
    round_forecasts: dict[int, RoundForecastNascar],
    source: NascarDataSource,
    year: int,
    ladder: dict,
    known_grid: list[str] | None = None,
) -> dict:
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    driver_rows, team_rows, make_rows = _standings_lists(source, year)

    next_round = _next_round(source, year)
    prediction = None
    if next_round is not None:
        # Reuse the round forecast already computed (conditioned on real
        # qualifying when ``known_grid`` is set), so the season summary, the
        # round detail page, and the post-quali grid all agree.
        fc = round_forecasts[next_round]
        race = fc.race
        post_quali = bool(known_grid)
        prediction = {
            "season": fc.season,
            "round": fc.round,
            "venueKey": fc.venue_key,
            "venueName": fc.venue_name,
            "raceName": fc.race_name,
            "trackType": fc.track_type,
            "phase": "post-quali" if post_quali else "pre",
            "qualifyingActual": post_quali,
            "qualifying": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME.get(c, c),
                    "team": config.TEAM_OF.get(c, ""),
                }
                for i, c in enumerate(race.grid, start=1)
            ],
            "race": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME.get(c, c),
                    "team": config.TEAM_OF.get(c, ""),
                    "pWin": round(race.markets.p_win.get(c, 0.0), 4),
                    "pPodium": round(race.markets.p_podium.get(c, 0.0), 4),
                    "pDnf": round(race.p_dnf.get(c, 0.0), 4),
                }
                for i, c in enumerate(race.order, start=1)
            ],
        }

    fmt = config.CUP_CURRENT_FORMAT
    return {
        "sport": config.SPORT,
        "season": year,
        "seasonLabel": config.season_label(year),
        "generatedAt": _now_iso(),
        "completedRounds": n_completed,
        "lastUpdatedRound": max(completed) if completed else 0,
        "totalRounds": len(config.CALENDAR),
        "regularSeasonRaces": fmt.regular_season_races,
        "playoffFieldSize": fmt.playoff_field_size,
        "calendar": [
            {
                "round": i,
                "key": meta["key"],
                "name": meta["track"],
                "raceName": meta["raceName"],
                "country": "United States",
                "kind": meta["kind"],
                "trackType": meta["trackType"],
                "stageLaps": list(meta.get("stageLaps") or []),
                "raceDate": meta.get("date", ""),
                "isPlayoff": i > fmt.regular_season_races,
                "completed": i in completed,
                "dataSource": source.provenance(year, i) if i in completed else None,
            }
            for i, meta in sorted(config.CALENDAR_META.items())
        ],
        "driverStandings": driver_rows,
        "teamStandings": team_rows,
        "manufacturerStandings": make_rows,
        "championship": _championship(source, year, ladder),
        "seasonAccuracy": _season_accuracy(round_forecasts, source, year),
        "nextPrediction": prediction,
    }


def _calibration_summary(calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    per_market = {m: 0 for m in calibration.MARKETS}
    strata: dict[str, list[str]] = {}
    if applied:
        counts = calibrator.sample_counts().get("global", {})
        if isinstance(counts, dict):
            per_market.update({m: int(counts.get(m, 0)) for m in calibration.MARKETS})
        strata = calibrator.strata_with_models()
    return {
        "generatedAt": _now_iso(),
        "applied": applied,
        "trainingRounds": real_rounds,
        "strata": strata,
        "dataLimitation": (
            "Calibrated on real NASCAR Cup results, stratified by track type "
            "(superspeedway / intermediate / short / road)."
            if applied
            else "Probability calibration turns on once "
            f"{config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds are backfilled."
        ),
        "perMarket": per_market,
    }


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rounds_dir = out_dir / "rounds"
    probs_dir = out_dir / "probabilities"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    probs_dir.mkdir(parents=True, exist_ok=True)

    source = NascarDataSource()
    year = config.SEASON
    completed_rounds = set(source.completed_rounds(year))

    # Honest calibration gate: fit only from real (non-synthetic) rounds.
    calibrator, real_rounds = build_calibrator(source, year)

    # Post-quali seam: if the upcoming round's REAL qualifying is published,
    # the next-round forecast conditions on the actual grid.
    next_round = _next_round(source, year)
    known_grid = source.qualifying(year, next_round) if next_round else None

    # Forecast every round once (leakage-safe — each uses only prior rounds).
    round_forecasts: dict[int, RoundForecastNascar] = {}
    for rnd in range(1, len(config.CALENDAR) + 1):
        fc = pipeline.forecast_round(
            source, year, rnd, known_grid=known_grid if rnd == next_round else None
        )
        round_forecasts[rnd] = fc
        completed = rnd in completed_rounds
        (rounds_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(round_payload(fc, source, completed), indent=2) + "\n"
        )
        (probs_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(probabilities_payload(fc, calibrator, real_rounds), indent=2) + "\n"
        )

    (out_dir / "calibration_summary.json").write_text(
        json.dumps(_calibration_summary(calibrator, real_rounds), indent=2) + "\n"
    )

    # Championship: one playoff ladder shared by nascar.json and the
    # dedicated playoff projection file (they must agree).
    ladder = pipeline.playoff_projection(source, year)
    (out_dir / "playoff_projection.json").write_text(
        json.dumps(playoff_projection_payload(source, year, ladder), indent=2) + "\n"
    )

    payload = build_payload(round_forecasts, source, year, ladder, known_grid=known_grid)
    path = out_dir / "nascar.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")

    # Multi-season index (current season + any archives under seasons/<year>/).
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
