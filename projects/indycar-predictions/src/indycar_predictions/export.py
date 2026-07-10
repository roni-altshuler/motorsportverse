"""Generate the IndyCar website's JSON data from the model + pipeline.

The website is a static export: it reads everything from ``public/data/`` at
build time, so this module is the single producer of that contract. It mirrors
the F1/F2/F3/FE/NASCAR fan-out shape so the IndyCar site reuses the family's
components 1:1, with the IndyCar-specific ``trackType``/``trackGroup`` extras
riding on every surface (the oval / road / street split is first-class here):

    public/data/
      indycar.json                season summary (calendar, standings,
                                  championship, next-round prediction,
                                  season accuracy)
      rounds/round_NN.json        per-round race classification, grid and (for
                                  completed rounds) actual results + accuracy
      probabilities/round_NN.json per-race market probabilities + H2H +
                                  calibration state (track-type strata)
      calibration_summary.json    honest calibration status
      seasons.json                multi-season index (current + archives)

The continuous-learning files (forward_eval/, model_health.json,
promotion_status.json, historical_backtest/, reliability_plots/) are written
by the sibling CLIs.

Run:  python -m indycar_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, pipeline
from .datasource import IndycarDataSource
from .model import RaceForecast, RoundForecastIndycar
from .sources.composite import CompositeIndycarSource

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
_FALLBACK_COLOR = "#D31217"  # IndyCar red

# Per-race H2H is only useful for the contenders; cap it so files stay small.
H2H_TOP_N = 12


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _headshot(code: str) -> str:
    return f"/headshots/{code}.webp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _actual_map(source: IndycarDataSource, year: int, rnd: int) -> dict[str, int]:
    return {r.competitor: r.position for r in source.results(year, rnd)}


def _next_round(source: IndycarDataSource, year: int) -> int | None:
    """The upcoming round number (the first not-yet-completed round), or None
    if the season is over. Source-derived so it stays correct as rounds complete."""
    completed = source.completed_rounds(year)
    nxt = (max(completed) + 1) if completed else 1
    return nxt if nxt <= len(config.CALENDAR) else None


def _team_color(team: str) -> str:
    return TEAM_COLOR.get(team, _FALLBACK_COLOR)


# --------------------------------------------------------------------------- #
# Per-round detail (rounds/round_NN.json)
# --------------------------------------------------------------------------- #
def _classification(race: RaceForecast, source: IndycarDataSource, actual: dict[str, int]) -> list[dict]:
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
                "engine": config.ENGINE_OF.get(code, ""),
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
    race: RaceForecast, source: IndycarDataSource, year: int, rnd: int, completed: bool
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
        status = {r["code"]: (r.get("status") or "Running") for r in rows}
        if status:
            block["actualStatus"] = status
        predicted = {code: i for i, code in enumerate(race.order, start=1)}
        block["accuracy"] = core_eval.score_round(predicted, actual)
    return block


def _model_config(fc: RoundForecastIndycar) -> dict:
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
    return {
        "positionModel": position,
        "dnfComposition": {"applied": True},
        "dualTrackElo": {"applied": True, "group": fc.track_group},
    }


def round_payload(fc: RoundForecastIndycar, source: IndycarDataSource, completed: bool) -> dict:
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
        "trackGroup": fc.track_group,
        "isIndy500": config.is_indy500_round(fc.round) if fc.season == config.SEASON else False,
        "raceDate": meta.get("date", ""),
        "completed": completed,
        "dataSource": data_source,  # "snapshot"/"wikipedia" (real) or "synthetic"
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

    IndyCar's calibration strata are the three track types — an oval forecast
    and a street forecast have very different variance and the calibrator
    learns each honestly from real outcomes. Falls back to the raw
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


def _race_probabilities(fc: RoundForecastIndycar, calibrator) -> dict:
    race = fc.race
    return {
        "raceType": race.race_type,
        "trackType": fc.track_type,
        "trackGroup": fc.track_group,
        "markets": _calibrate_markets(race, calibrator, fc.track_type),
        "dnf": {c: round(p, 4) for c, p in race.p_dnf.items()},
        "h2h": _h2h_subset(race),
        "method": "monte-carlo-dnf-composed",
        "monteCarloSamples": race.n_samples,
        "temperature": race.temperature,
    }


def probabilities_payload(fc: RoundForecastIndycar, calibrator, real_rounds: int) -> dict:
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


def build_calibrator(source: IndycarDataSource, year: int):
    """Fit a track-type-stratified probability calibrator from *real*
    completed rounds.

    Counts only rounds whose results came from a real source (not synthetic).
    Below ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it returns
    ``(None, count)`` so the site honestly reports calibration as
    not-yet-applied.
    """
    real_rounds = [
        r
        for r in source.completed_rounds(year)
        if CompositeIndycarSource.is_real(source.provenance(year, r))
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
# Championship (straight points, no playoffs)
# --------------------------------------------------------------------------- #
def _max_points_per_round() -> float:
    return float(
        config.POINTS[1]
        + config.POLE_BONUS
        + config.LED_LAP_BONUS
        + config.MOST_LAPS_LED_BONUS
    )


def _championship(source: IndycarDataSource, year: int) -> list[dict]:
    title = pipeline.project_title(source, year)
    leader_points = max((t.current_points for t in title), default=0.0)
    remaining = len(config.CALENDAR) - len(source.completed_rounds(year))
    ceiling = remaining * _max_points_per_round()
    out: list[dict] = []
    for t in title:
        max_attainable = t.current_points + ceiling
        out.append(
            {
                "code": t.key,
                "name": config.DRIVER_NAME.get(t.key, t.key),
                "team": config.TEAM_OF.get(t.key, ""),
                "engine": config.ENGINE_OF.get(t.key, ""),
                "pTitle": round(t.p_title, 4),
                "currentPoints": t.current_points,
                "projMean": t.proj_mean,
                "projP10": t.proj_p10,
                "projP90": t.proj_p90,
                "maxAttainable": max_attainable,
                "canStillWin": max_attainable >= leader_points,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Season accuracy (leakage-safe per-round predictions vs actual)
# --------------------------------------------------------------------------- #
def _season_accuracy(
    round_forecasts: dict[int, RoundForecastIndycar], source: IndycarDataSource, year: int
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
def _per_round_stats(source: IndycarDataSource, year: int) -> dict[str, dict]:
    """Wins/podiums/top10s + cumulative awarded-points history per driver."""
    stats: dict[str, dict] = {}
    completed = source.completed_rounds(year)
    running: dict[str, float] = {}
    for i, rnd in enumerate(completed):
        rows = source.race_rows(year, rnd) or []
        for r in rows:
            code = r["code"]
            d = stats.setdefault(
                code, {"wins": 0, "podiums": 0, "top10s": 0, "history": []}
            )
            pos = r.get("position") or 0
            d["wins"] += 1 if pos == 1 else 0
            d["podiums"] += 1 if 0 < pos <= 3 else 0
            d["top10s"] += 1 if 0 < pos <= 10 else 0
            pts = r.get("points")
            if pts is None and pos:
                pts = float(config.POINTS.get(int(pos), 5))
            running[code] = running.get(code, 0.0) + float(pts or 0.0)
        for code, d in stats.items():
            # Pad the history for drivers who joined mid-season.
            h = d["history"]
            h.extend([h[-1] if h else 0.0] * (i - len(h)))
            h.append(running.get(code, 0.0))
    return stats


def _standings_lists(source: IndycarDataSource, year: int) -> tuple[list[dict], list[dict], list[dict]]:
    """(driverStandings, teamStandings, engineStandings).

    Driver standings come from the curated official grid (points AS AWARDED)
    when the source is real, enriched with wins/podiums/points history from
    the round rows; team/engine standings are computed sums of the same
    awarded points (IndyCar's entrant/manufacturer tables use eligibility
    rules we don't model — these are labelled computed on the site).
    """
    official = pipeline.official_standings(source, year)
    stats = _per_round_stats(source, year)
    n_completed = len(source.completed_rounds(year))

    if official:
        driver_rows = []
        for d in official:
            code = d["code"]
            s = stats.get(code, {"wins": 0, "podiums": 0, "top10s": 0, "history": []})
            h = list(s["history"])
            h = h + [h[-1] if h else 0.0] * (n_completed - len(h))
            team = config.TEAM_OF.get(code, "")
            driver_rows.append(
                {
                    "position": d["position"],
                    "code": code,
                    "name": d.get("name", code),
                    "team": team,
                    "engine": config.ENGINE_OF.get(code, ""),
                    "teamColor": _team_color(team),
                    "points": float(d["points"]),
                    "wins": int(s["wins"]),
                    "podiums": int(s["podiums"]),
                    "top10s": int(s["top10s"]),
                    "pointsHistory": h,
                }
            )
    else:
        # Fallback: recompute from the source's results (synthetic / no snapshot).
        ds = pipeline.driver_standings(source, year)
        driver_rows = [
            {
                "position": i,
                "code": r.key,
                "name": config.DRIVER_NAME.get(r.key, r.key),
                "team": config.TEAM_OF.get(r.key, ""),
                "engine": config.ENGINE_OF.get(r.key, ""),
                "teamColor": _team_color(config.TEAM_OF.get(r.key, "")),
                "points": r.points,
                "wins": r.wins,
                "podiums": r.podiums,
                "top10s": 0,
                "pointsHistory": [],
            }
            for i, r in enumerate(ds, start=1)
        ]

    # Team / engine standings: awarded points summed by group.
    team_pts: dict[str, dict] = {}
    engine_pts: dict[str, dict] = {}
    for row in driver_rows:
        for group_key, table in (("team", team_pts), ("engine", engine_pts)):
            g = row.get(group_key) or ""
            if not g:
                continue
            slot = table.setdefault(g, {"points": 0.0, "wins": 0})
            slot["points"] += float(row["points"])
            slot["wins"] += int(row["wins"])
    team_rows = [
        {
            "position": i,
            "team": g,
            "teamColor": _team_color(g),
            "points": v["points"],
            "wins": v["wins"],
        }
        for i, (g, v) in enumerate(
            sorted(team_pts.items(), key=lambda kv: (-kv[1]["points"], kv[0])), start=1
        )
    ]
    engine_rows = [
        {
            "position": i,
            "engine": g,
            "color": config.ENGINE_COLORS.get(g, _FALLBACK_COLOR),
            "points": v["points"],
            "wins": v["wins"],
        }
        for i, (g, v) in enumerate(
            sorted(engine_pts.items(), key=lambda kv: (-kv[1]["points"], kv[0])), start=1
        )
    ]
    return driver_rows, team_rows, engine_rows


# --------------------------------------------------------------------------- #
# Top-level builders
# --------------------------------------------------------------------------- #
def build_payload(
    round_forecasts: dict[int, RoundForecastIndycar],
    source: IndycarDataSource,
    year: int,
    known_grid: list[str] | None = None,
) -> dict:
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    driver_rows, team_rows, engine_rows = _standings_lists(source, year)

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
            "trackGroup": fc.track_group,
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

    return {
        "sport": config.SPORT,
        "season": year,
        "seasonLabel": config.season_label(year),
        "generatedAt": _now_iso(),
        "completedRounds": n_completed,
        "lastUpdatedRound": max(completed) if completed else 0,
        "totalRounds": len(config.CALENDAR),
        "trackTypeCounts": {
            t: sum(1 for m in config.CALENDAR_META.values() if m["trackType"] == t)
            for t in config.TRACK_TYPES
        },
        "calendar": [
            {
                "round": i,
                "key": meta["key"],
                "name": meta["venue"],
                "raceName": meta["raceName"],
                "country": "United States",
                "kind": meta["kind"],
                "trackType": meta["trackType"],
                "trackGroup": config.track_group_of(meta["trackType"]),
                "isIndy500": config.is_indy500_round(i),
                "raceDate": meta.get("date", ""),
                "completed": i in completed,
                "dataSource": source.provenance(year, i) if i in completed else None,
            }
            for i, meta in sorted(config.CALENDAR_META.items())
        ],
        "driverStandings": driver_rows,
        "teamStandings": team_rows,
        "engineStandings": engine_rows,
        "championship": _championship(source, year),
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
            "Calibrated on real IndyCar results, stratified by track type "
            "(oval / road / street)."
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

    source = IndycarDataSource()
    year = config.SEASON
    completed_rounds = set(source.completed_rounds(year))

    # Honest calibration gate: fit only from real (non-synthetic) rounds.
    calibrator, real_rounds = build_calibrator(source, year)

    # Post-quali seam: if the upcoming round's REAL qualifying is published
    # (refresh stores it in the snapshot's optional ``qualifying`` block), the
    # next-round forecast conditions on the actual grid.
    next_round = _next_round(source, year)
    known_grid = source.qualifying(year, next_round) if next_round else None

    # Forecast every round once (leakage-safe — each uses only prior rounds).
    round_forecasts: dict[int, RoundForecastIndycar] = {}
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

    payload = build_payload(round_forecasts, source, year, known_grid=known_grid)
    path = out_dir / "indycar.json"
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
