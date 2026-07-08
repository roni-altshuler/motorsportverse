"""Generate the FE website's JSON data from the model + pipeline.

The website is a static export: it reads everything from ``public/data/`` at
build time, so this module is the single producer of that contract. It mirrors
the F1/F2/F3 fan-out shape so the FE site reuses the family's components 1:1:

    public/data/
      fe.json                     season summary (calendar, standings, championship,
                                  next-round prediction, season accuracy)
      rounds/round_NN.json        per-round race classification, grid, and (for
                                  completed rounds) actual results + accuracy
      probabilities/round_NN.json per-race market probabilities + H2H + calibration state
      calibration_summary.json    honest calibration status
      seasons.json                multi-season index (current + archives under seasons/<year>/)

The continuous-learning files (forward_eval/, model_health.json,
promotion_status.json, historical_backtest/, reliability_plots/) are written by
the sibling CLIs.

Run:  python -m formula_e_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, model, pipeline
from .datasource import FEDataSource
from .model import RaceForecast, RoundForecastFE
from .sources.composite import CompositeFESource

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"


def out_dir_for_season(year: int, base: Path = DEFAULT_OUT) -> Path:
    """Data root for a season's website files.

    The ACTIVE season lives at the top level of ``website/public/data`` (so the
    current-season contract never moves); ARCHIVED seasons live under
    ``seasons/<year>/`` (created by ``season_rollover.py``).
    """
    return base if int(year) == int(config.SEASON) else base / "seasons" / str(year)


def write_seasons_index(out_dir: Path = DEFAULT_OUT, current: int | None = None) -> dict:
    """Write ``seasons.json`` — the multi-season index the website reads to
    know which seasons exist and which is current.

    Archived years are discovered by scanning ``<out_dir>/seasons/``; the
    frontend resolves a season's base path as ``/data`` when current, else
    ``/data/seasons/<year>``. Labels carry FE's split-year form ("2025-26").
    """
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
                "label": f"{y - 1}-{str(y)[2:]}",
            }
            for y in available
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seasons.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


# Single source of truth for team colours — straight from config, never duplicated.
TEAM_COLOR: dict[str, str] = {t.name: t.color for t in config.TEAMS}
_FALLBACK_COLOR = "#00A19C"  # FE electric teal

# Per-race H2H is only useful for the contenders; cap it so files stay small.
H2H_TOP_N = 10


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _headshot(code: str) -> str:
    return f"/headshots/{code}.webp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _actual_map(source: FEDataSource, year: int, rnd: int) -> dict[str, int]:
    return {r.competitor: r.position for r in source.results(year, rnd)}


def _next_round(source: FEDataSource, year: int) -> int | None:
    """The upcoming round number (the first not-yet-completed round), or None
    if the season is over. Feed-derived so it stays correct as rounds complete."""
    completed = source.completed_rounds(year)
    nxt = (max(completed) + 1) if completed else 1
    return nxt if nxt <= len(config.CALENDAR) else None


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
                "team": team,
                "teamColor": TEAM_COLOR.get(team, _FALLBACK_COLOR),
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


def _race_block(race: RaceForecast, source: FEDataSource, year: int, rnd: int, completed: bool) -> dict:
    actual = _actual_map(source, year, rnd) if completed else {}
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


def _model_config(fc: RoundForecastFE) -> dict:
    """A/B lever provenance for the round — mirrors F1's ``modelConfig`` block.

    ``positionModel`` records whether the opt-in finishing-position head
    (:mod:`.position_head`, gated by ``FE_USE_POSITION_HEAD``, default OFF)
    re-ranked this forecast.
    """
    head = fc.position_head
    position: dict = {"applied": bool(head.get("applied", False)) if head else False}
    if head:
        if head.get("trainedRounds") is not None:
            position["trainedRounds"] = [int(r) for r in head["trainedRounds"]]
        if head.get("trainRows") is not None:
            position["trainRows"] = int(head["trainRows"])
        if head.get("reason"):
            position["reason"] = str(head["reason"])
    return {"positionModel": position}


def round_payload(fc: RoundForecastFE, source: FEDataSource, completed: bool) -> dict:
    data_source = source.provenance(fc.season, fc.round) if completed else None
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "country": fc.country,
        "venueKind": fc.venue_kind,
        "completed": completed,
        "dataSource": data_source,  # "snapshot"/"pulselive" (real) or "synthetic"
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
    """Per-market probabilities, calibrated per venue-kind stratum when fitted.

    FE's calibration strata are ``street`` vs ``circuit`` — street racing is
    higher-variance and the calibrator learns exactly how much from real
    outcomes. Falls back to the raw Monte-Carlo probability when the
    (market, stratum) has no fitted model — always honest about what was
    calibrated.
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


def _race_probabilities(fc: RoundForecastFE, calibrator) -> dict:
    race = fc.race
    return {
        "raceType": race.race_type,
        "venueKind": fc.venue_kind,
        "markets": _calibrate_markets(race, calibrator, fc.venue_kind),
        "h2h": _h2h_subset(race),
        "method": "monte-carlo",
        "monteCarloSamples": race.n_samples,
        "temperature": race.temperature,
    }


def probabilities_payload(fc: RoundForecastFE, calibrator, real_rounds: int) -> dict:
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


def build_calibrator(source: FEDataSource, year: int):
    """Fit a venue-kind-stratified probability calibrator from *real* completed
    rounds.

    Counts only rounds whose results came from a real feed (not synthetic).
    Below ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it returns ``(None, count)``
    so the site honestly reports calibration as not-yet-applied.
    """
    real_rounds = [
        r
        for r in source.completed_rounds(year)
        if CompositeFESource.is_real(source.provenance(year, r))
    ]
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)

    records: list[dict] = []
    for rnd in real_rounds:
        fc = pipeline.forecast_round(source, year, rnd)
        actual = _actual_map(source, year, rnd)
        recs = calibration.collect_history_from_rounds({rnd: fc.race.markets}, {rnd: actual})
        for rec in recs:
            rec["stratum"] = fc.venue_kind
        records.extend(recs)

    calibrator = calibration.StratifiedProbabilityCalibrator().fit_from_history(records)
    return (calibrator if calibrator.is_fitted() else None), len(real_rounds)


# --------------------------------------------------------------------------- #
# Championship with can-still-win math
# --------------------------------------------------------------------------- #
def _max_points_per_round() -> int:
    return max(config.POINTS.values()) + config.POLE_POINTS + config.FASTEST_LAP_POINTS


def _championship(source: FEDataSource, year: int) -> list[dict]:
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
    round_forecasts: dict[int, RoundForecastFE], source: FEDataSource, year: int
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
# Top-level builders
# --------------------------------------------------------------------------- #
def _points_history(source: FEDataSource, year: int) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """Cumulative driver- and team-points after each completed round
    (recomputed fallback — the official snapshot carries exact histories)."""
    from motorsport_core import standings as core_standings

    driver_codes = [d["code"] for d in config.DRIVERS]
    teams = list(dict.fromkeys(config.TEAM_OF.values()))
    driver_hist: dict[str, list[float]] = {c: [] for c in driver_codes}
    team_hist: dict[str, list[float]] = {t: [] for t in teams}

    races: list[dict[str, int]] = []
    for rnd in source.completed_rounds(year):
        races.append({r.competitor: r.position for r in source.results(year, rnd)})
        d_rows = core_standings.compute_driver_standings(races, config.POINTS)
        d_points = {row.key: row.points for row in d_rows}
        for c in driver_codes:
            driver_hist[c].append(d_points.get(c, 0))
        t_rows = core_standings.compute_team_standings(races, config.POINTS, config.TEAM_OF)
        t_points = {row.key: row.points for row in t_rows}
        for t in teams:
            team_hist[t].append(t_points.get(t, 0))
    return driver_hist, team_hist


def _standings_lists(source: FEDataSource, year: int) -> tuple[list[dict], list[dict]]:
    """(driverStandings, teamStandings) for fe.json — official snapshot totals
    when the feed is real (exact, incl. pole/FL bonuses), else recomputed."""
    official = pipeline.official_standings(source, year)
    if official:
        drivers = official.get("driverStandings", [])
        teams = official.get("teamStandings", [])
        team_wp: dict[str, dict[str, int]] = {}
        for d in drivers:
            wp = team_wp.setdefault(d.get("team", ""), {"wins": 0, "podiums": 0})
            wp["wins"] += int(d.get("wins", 0))
            wp["podiums"] += int(d.get("podiums", 0))
        driver_rows = [
            {
                "position": d["position"],
                "code": d["code"],
                "name": d.get("name", d["code"]),
                "team": d.get("team", ""),
                "teamColor": TEAM_COLOR.get(d.get("team", ""), _FALLBACK_COLOR),
                "points": d["points"],
                "wins": int(d.get("wins", 0)),
                "podiums": int(d.get("podiums", 0)),
                "pointsHistory": d.get("pointsHistory", []),
            }
            for d in drivers
        ]
        team_rows = [
            {
                "position": t["position"],
                "team": t["team"],
                "teamColor": TEAM_COLOR.get(t["team"], _FALLBACK_COLOR),
                "points": t["points"],
                "wins": team_wp.get(t["team"], {}).get("wins", 0),
                "podiums": team_wp.get(t["team"], {}).get("podiums", 0),
                "pointsHistory": t.get("pointsHistory", []),
            }
            for t in teams
        ]
        return driver_rows, team_rows

    # Fallback: recompute from the source's results (synthetic / no snapshot).
    ds = pipeline.driver_standings(source, year)
    ts = pipeline.team_standings(source, year)
    driver_hist, team_hist = _points_history(source, year)
    driver_rows = [
        {
            "position": i,
            "code": r.key,
            "name": config.DRIVER_NAME.get(r.key, r.key),
            "team": config.TEAM_OF.get(r.key, ""),
            "teamColor": TEAM_COLOR.get(config.TEAM_OF.get(r.key, ""), _FALLBACK_COLOR),
            "points": r.points,
            "wins": r.wins,
            "podiums": r.podiums,
            "pointsHistory": driver_hist.get(r.key, []),
        }
        for i, r in enumerate(ds, start=1)
    ]
    team_rows = [
        {
            "position": i,
            "team": r.key,
            "teamColor": TEAM_COLOR.get(r.key, _FALLBACK_COLOR),
            "points": r.points,
            "wins": r.wins,
            "podiums": r.podiums,
            "pointsHistory": team_hist.get(r.key, []),
        }
        for i, r in enumerate(ts, start=1)
    ]
    return driver_rows, team_rows


def build_payload(
    round_forecasts: dict[int, RoundForecastFE],
    source: FEDataSource,
    year: int,
    known_grid: list[str] | None = None,
) -> dict:
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    driver_rows, team_rows = _standings_lists(source, year)

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
            # "post-quali" once the real grid is locked, else "pre".
            "phase": "post-quali" if post_quali else "pre",
            "qualifyingActual": post_quali,
            "qualifying": [
                {"position": i, "code": c, "name": config.DRIVER_NAME[c], "team": config.TEAM_OF[c]}
                for i, c in enumerate(race.grid, start=1)
            ],
            "race": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME[c],
                    "team": config.TEAM_OF[c],
                    "pWin": round(race.markets.p_win.get(c, 0.0), 4),
                    "pPodium": round(race.markets.p_podium.get(c, 0.0), 4),
                }
                for i, c in enumerate(race.order, start=1)
            ],
        }

    meta = config.CALENDAR_META
    return {
        "sport": config.SPORT,
        "season": year,
        "seasonLabel": config.season_label(year),
        "generatedAt": _now_iso(),
        "completedRounds": n_completed,
        "lastUpdatedRound": max(completed) if completed else 0,
        "totalRounds": len(config.CALENDAR),
        "calendar": [
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "kind": model._kind_str(v),
                "city": meta.get(i, {}).get("city", ""),
                "raceDate": meta.get(i, {}).get("date", ""),
                "completed": i in completed,
                "dataSource": source.provenance(year, i) if i in completed else None,
            }
            for i, v in enumerate(config.CALENDAR, start=1)
        ],
        "driverStandings": driver_rows,
        "teamStandings": team_rows,
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
            "Calibrated on real Formula E results, stratified street vs permanent circuit."
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

    source = FEDataSource()
    year = config.SEASON
    completed_rounds = set(source.completed_rounds(year))

    # Honest calibration gate: fit only from real (non-synthetic) rounds.
    calibrator, real_rounds = build_calibrator(source, year)

    # Post-quali seam: if the upcoming round's REAL qualifying is published,
    # the next-round forecast conditions on the actual grid.
    next_round = _next_round(source, year)
    known_grid = source.qualifying(year, next_round) if next_round else None

    # Forecast every round once (leakage-safe — each uses only prior rounds).
    round_forecasts: dict[int, RoundForecastFE] = {}
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
    path = out_dir / "fe.json"
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
