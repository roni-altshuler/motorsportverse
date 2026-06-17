"""Generate the F2 website's JSON data from the model + pipeline.

The website is a static export: it reads everything from ``public/data/`` at build
time, so this module is the single producer of that contract. It mirrors the F1
flagship's fan-out shape so the two sites can share components 1:1:

    public/data/
      f2.json                     season summary (calendar, standings, championship,
                                  next-round prediction, season accuracy)
      rounds/round_NN.json        per-round sprint + feature classification, grid,
                                  and (for completed rounds) actual results + accuracy
      probabilities/round_NN.json per-race market probabilities + H2H + calibration state
      calibration_summary.json    honest calibration status (Phase 1: not yet applied)

The continuous-learning files (forward_eval/, model_health.json, promotion_status.json)
are written by the sibling CLIs, which need real actuals to be meaningful.

Run:  python -m f2_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, model, pipeline
from .datasource import F2DataSource
from .model import RaceForecast, RoundForecastF2
from .sources.composite import CompositeF2Source

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# Single source of truth for team colours — straight from config, never duplicated.
TEAM_COLOR: dict[str, str] = {t.name: t.color for t in config.TEAMS}

# Per-race H2H is only useful for the contenders; cap it so files stay small and
# the on-site matrix stays readable.
H2H_TOP_N = 10


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _headshot(code: str) -> str:
    return f"/headshots/{code}.webp"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _actual_map(source: F2DataSource, year: int, rnd: int, race_type: str) -> dict[str, int]:
    results = source.race_results_for_round(year, rnd)[race_type]
    return {r.competitor: r.position for r in results}


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
                "teamColor": TEAM_COLOR.get(team, "#1E9BD7"),
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
    race: RaceForecast, source: F2DataSource, year: int, rnd: int, completed: bool
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


def round_payload(fc: RoundForecastF2, source: F2DataSource, completed: bool) -> dict:
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "country": fc.country,
        "completed": completed,
        "dataSource": "synthetic",  # Phase 1; flips to the live feed in Phase 2
        "sprint": _race_block(fc.sprint, source, fc.season, fc.round, completed),
        "feature": _race_block(fc.feature, source, fc.season, fc.round, completed),
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


def _calibrate_markets(race: RaceForecast, calibrator) -> dict:
    """Per-market probabilities, calibrated per race-type stratum when fitted.

    Falls back to the raw Monte-Carlo probability when the (market, stratum) has
    no fitted model — so the output is always honest about what was calibrated.
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
        if calibrator is not None and calibrator.is_fitted(market, race.race_type):
            cal_vals = calibrator.transform(market, raw_vals, stratum=race.race_type)
        else:
            cal_vals = raw_vals
        out[market] = {
            c: {"probability": round(float(cal_vals[i]), 4), "rawProbability": round(float(raw_vals[i]), 4)}
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


def probabilities_payload(fc: RoundForecastF2, calibrator, real_rounds: int) -> dict:
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


def build_calibrator(source: F2DataSource, year: int):
    """Fit a per-race-type probability calibrator from *real* completed rounds.

    Counts only rounds whose results came from a real feed (not synthetic). Below
    ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it returns ``(None, count)`` so the
    site honestly reports calibration as not-yet-applied — the F1 gate, ported.
    """
    real_rounds = [
        r
        for r in range(1, config.COMPLETED_ROUNDS + 1)
        if CompositeF2Source.is_real(source.provenance(year, r, race_index=1))
    ]
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)

    records: list[dict] = []
    for rnd in real_rounds:
        fc = pipeline.forecast_round(source, year, rnd)
        for race, race_type in ((fc.feature, model.FEATURE), (fc.sprint, model.SPRINT)):
            actual = _actual_map(source, year, rnd, race_type)
            recs = calibration.collect_history_from_rounds({rnd: race.markets}, {rnd: actual})
            for rec in recs:
                rec["stratum"] = race_type
            records.extend(recs)

    calibrator = calibration.StratifiedProbabilityCalibrator().fit_from_history(records)
    return (calibrator if calibrator.is_fitted() else None), len(real_rounds)


# --------------------------------------------------------------------------- #
# Championship with can-still-win math
# --------------------------------------------------------------------------- #
def _max_points_per_round() -> int:
    return (
        max(config.SPRINT_POINTS.values())
        + max(config.FEATURE_POINTS.values())
        + config.POLE_POINTS
        + config.FASTEST_LAP_POINTS
    )


def _championship(source: F2DataSource, year: int) -> list[dict]:
    title = pipeline.project_title(source, year)
    leader_points = max((t.current_points for t in title), default=0.0)
    remaining = len(config.CALENDAR) - config.COMPLETED_ROUNDS
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
# Season accuracy (feature-race, leakage-safe per-round predictions vs actual)
# --------------------------------------------------------------------------- #
def _season_accuracy(round_forecasts: dict[int, RoundForecastF2], source: F2DataSource, year: int) -> dict:
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
# Top-level builders
# --------------------------------------------------------------------------- #
def build_payload(round_forecasts: dict[int, RoundForecastF2], source: F2DataSource, year: int) -> dict:
    driver_standings = pipeline.driver_standings(source, year)
    teams = pipeline.team_standings(source, year)

    next_round = config.COMPLETED_ROUNDS + 1
    prediction = None
    if next_round <= len(config.CALENDAR):
        pred = pipeline.predict_round(source, year, next_round)
        prediction = {
            "season": pred.season,
            "round": pred.round,
            "venueKey": pred.venue_key,
            "venueName": pred.venue_name,
            "qualifying": [
                {"position": i, "code": c, "name": config.DRIVER_NAME[c], "team": config.TEAM_OF[c]}
                for i, c in enumerate(pred.qualifying_order, start=1)
            ],
            "race": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME[c],
                    "team": config.TEAM_OF[c],
                    "pWin": round(pred.p_win.get(c, 0.0), 4),
                    "pPodium": round(pred.p_podium.get(c, 0.0), 4),
                }
                for i, c in enumerate(pred.race_order, start=1)
            ],
        }

    return {
        "sport": config.SPORT,
        "season": year,
        "generatedAt": _now_iso(),
        "completedRounds": config.COMPLETED_ROUNDS,
        "lastUpdatedRound": config.COMPLETED_ROUNDS,
        "totalRounds": len(config.CALENDAR),
        "calendar": [
            {
                "round": i,
                "key": v.key,
                "name": v.name,
                "country": v.country,
                "completed": i <= config.COMPLETED_ROUNDS,
                "dataSource": "synthetic" if i <= config.COMPLETED_ROUNDS else None,
            }
            for i, v in enumerate(config.CALENDAR, start=1)
        ],
        "driverStandings": [
            {
                "position": i,
                "code": r.key,
                "name": config.DRIVER_NAME.get(r.key, r.key),
                "team": config.TEAM_OF.get(r.key, ""),
                "teamColor": TEAM_COLOR.get(config.TEAM_OF.get(r.key, ""), "#1E9BD7"),
                "points": r.points,
                "wins": r.wins,
                "podiums": r.podiums,
            }
            for i, r in enumerate(driver_standings, start=1)
        ],
        "teamStandings": [
            {
                "position": i,
                "team": r.key,
                "teamColor": TEAM_COLOR.get(r.key, "#1E9BD7"),
                "points": r.points,
                "wins": r.wins,
                "podiums": r.podiums,
            }
            for i, r in enumerate(teams, start=1)
        ],
        "championship": _championship(source, year),
        "seasonAccuracy": _season_accuracy(round_forecasts, source, year),
        "nextPrediction": prediction,
    }


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
            "Calibrated on real F2 results."
            if applied
            else "F2 runs on a synthetic source by default; probability calibration turns on "
            f"once {config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds are backfilled "
            "(set F2_USE_LIVE_RESULTS=1 with a live feed)."
        ),
        "perMarket": per_market,
    }


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rounds_dir = out_dir / "rounds"
    probs_dir = out_dir / "probabilities"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    probs_dir.mkdir(parents=True, exist_ok=True)

    source = F2DataSource()
    year = config.SEASON

    # Honest calibration gate: fit only from real (non-synthetic) rounds.
    calibrator, real_rounds = build_calibrator(source, year)

    # Forecast every round once (leakage-safe — each uses only prior rounds).
    round_forecasts: dict[int, RoundForecastF2] = {}
    for rnd in range(1, len(config.CALENDAR) + 1):
        fc = pipeline.forecast_round(source, year, rnd)
        round_forecasts[rnd] = fc
        completed = rnd <= config.COMPLETED_ROUNDS
        (rounds_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(round_payload(fc, source, completed), indent=2) + "\n"
        )
        (probs_dir / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(probabilities_payload(fc, calibrator, real_rounds), indent=2) + "\n"
        )

    (out_dir / "calibration_summary.json").write_text(
        json.dumps(_calibration_summary(calibrator, real_rounds), indent=2) + "\n"
    )

    payload = build_payload(round_forecasts, source, year)
    path = out_dir / "f2.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
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
