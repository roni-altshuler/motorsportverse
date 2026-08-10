"""Generate the WRC website's JSON data from the model + committed snapshots.

The website is a static export: it reads everything from ``public/data/`` at build
time, so this module is the single producer of that contract. It mirrors the
MotoGP golden template's fan-out shape so the two sites can share components 1:1 —
adapted to rally, where the differences are load-bearing:

* **One scored classification per round.** A rally is a single finishing order, so
  each round carries one ``rally`` block (no sprint, no qualifying grid, no
  race_index). There is no grid to condition on and no post-quali surface.
* **The surface defines the discipline.** Gravel / tarmac / snow are almost
  different sports, so every round and calendar entry surfaces its ``surface`` (and
  ``surfaceColor``) prominently.
* **Two championships.** Drivers *and* Manufacturers — both taken directly from the
  snapshot's official standings (the constructors' championship for manufacturers).

    public/data/
      wrc.json                    season summary (calendar w/ surface, driver +
                                  manufacturer standings, championship, next-round
                                  prediction, season accuracy)
      rounds/round_NN.json        per-round rally classification + (for completed
                                  rounds) actual results + accuracy
      probabilities/round_NN.json per-round market probabilities + H2H + calibration
      calibration_summary.json    honest calibration status (real corpus -> applied)
      seasons.json                multi-season index (current + archives)

The continuous-learning files (forward_eval/, model_health.json) are written by the
sibling :mod:`wrc_predictions.forward_eval` CLI, which needs real actuals.

Every forecast is leakage-safe (each round's pace uses only prior rounds and prior
seasons). The published forecast is the **ensemble** of the surface-aware skill
model with a championship-form prior — validated to beat a standings-order baseline
on the live season (see forward_eval).

Run:  python -m wrc_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, model
from .datasource import WrcDataSource
from .model import RallyForecast, RoundForecast

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

_NEUTRAL = "#8A8A8A"
# Per-round H2H is only useful for the contenders; cap it so files stay small.
H2H_TOP_N = 12
# Points-table ceiling per round for the can-still-win math (base Rally1 points;
# matches the deterministic points model the championship projection accumulates).
_MAX_POINTS_PER_ROUND = max(config.FEATURE_POINTS.values())

# Manufacturer short-name -> brand colour (config's palette); the official
# constructors'-championship entry names are long ("TOYOTA GAZOO RACING WRT"), so
# the display colour is resolved by substring match against these short names.
_MAN_COLORS: dict[str, str] = {t.name: t.color for t in config.TEAMS}


def out_dir_for_season(year: int, base: Path = DEFAULT_OUT) -> Path:
    """Data root for a season's website files: the ACTIVE season at the top level,
    ARCHIVED seasons under ``seasons/<year>/`` (mirrors the F1/MotoGP layout)."""
    return base if int(year) == int(config.SEASON) else base / "seasons" / str(year)


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _surface_color(surface: str) -> str:
    return config.SURFACE_COLORS.get(surface, _NEUTRAL)


def _manufacturer_color(name: str) -> str:
    up = (name or "").upper()
    for short, color in _MAN_COLORS.items():
        if short.upper() in up:
            return color
    return _NEUTRAL


def _actual_map(source: WrcDataSource, year: int, rnd: int) -> dict[str, int]:
    return {r.competitor: r.position for r in source.results(year, rnd) if r.position is not None}


def _next_round(source: WrcDataSource, year: int) -> int | None:
    """The upcoming round (first not-yet-completed), or None if the season is over."""
    completed = source.completed_rounds(year)
    nxt = (max(completed) + 1) if completed else 1
    return nxt if nxt <= len(config.CALENDAR) else None


# --------------------------------------------------------------------------- #
# Per-round detail (rounds/round_NN.json)
# --------------------------------------------------------------------------- #
def _classification(rally: RallyForecast, actual: dict[str, int]) -> list[dict]:
    m = rally.markets
    rows: list[dict] = []
    for pos, code in enumerate(rally.order, start=1):
        team = config.TEAM_OF.get(code, "Privateer")
        rows.append(
            {
                "position": pos,
                "code": code,
                "name": config.DRIVER_NAME.get(code, code),
                "nationality": config.DRIVER_NATION.get(code),
                "team": team,
                "teamColor": _MAN_COLORS.get(team, _NEUTRAL),
                "predictedValue": round(rally.score[code], 3),
                "pWin": round(m.p_win.get(code, 0.0), 4),
                "pPodium": round(m.p_podium.get(code, 0.0), 4),
                "pTop6": round(m.p_top6.get(code, 0.0), 4),
                "pTop10": round(m.p_top10.get(code, 0.0), 4),
                "meanFinish": round(rally.mean_finish[code], 2),
                "finishRangeLow": rally.range_low[code],
                "finishRangeHigh": rally.range_high[code],
                "confidence": rally.confidence.get(code, "Medium"),
                "actualPosition": actual.get(code),
            }
        )
    return rows


def _rally_block(
    rally: RallyForecast, source: WrcDataSource, year: int, rnd: int, completed: bool
) -> dict:
    actual = _actual_map(source, year, rnd) if completed else {}
    block: dict = {
        "surface": rally.surface,
        "surfaceColor": _surface_color(rally.surface),
        "classification": _classification(rally, actual),
    }
    if completed and actual:
        block["actualResults"] = [
            {"position": pos, "code": code}
            for code, pos in sorted(actual.items(), key=lambda kv: kv[1])
        ]
        predicted = {code: i for i, code in enumerate(rally.order, start=1)}
        block["accuracy"] = core_eval.score_round(predicted, actual)
    return block


def _model_config(surface: str) -> dict:
    """Model-lever provenance for the round. Rally has no qualifying grid and no
    finishing-position head, so the only production lever is the **ensemble** of the
    surface-aware skill model with the championship-form prior — surfaced honestly
    (no fabricated grid/position-model fields)."""
    return {
        "ensemble": {"applied": True, "modelWeight": config.ENSEMBLE_MODEL_WEIGHT},
        "surface": surface,
    }


def round_payload(fc: RoundForecast, source: WrcDataSource, completed: bool) -> dict:
    data_source = source.provenance(fc.season, fc.round) if completed else None
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "country": fc.country,
        "surface": fc.surface,
        "surfaceColor": _surface_color(fc.surface),
        "date": config.CALENDAR_META.get(fc.round, {}).get("date", ""),
        "completed": completed,
        "dataSource": data_source,  # real provenance ("snapshot") for completed rounds
        "modelConfig": _model_config(fc.surface),
        "rally": _rally_block(fc.rally, source, fc.season, fc.round, completed),
    }


# --------------------------------------------------------------------------- #
# Per-round probabilities (probabilities/round_NN.json)
# --------------------------------------------------------------------------- #
def _h2h_subset(rally: RallyForecast) -> dict[str, dict[str, float]]:
    """Head-to-head matrix restricted to the round's top contenders."""
    top = list(rally.order[:H2H_TOP_N])
    h2h = rally.markets.h2h
    return {
        a: {b: round(h2h[a][b], 4) for b in top if b in h2h.get(a, {})}
        for a in top
        if a in h2h
    }


_RAW_MARKET_KEYS = ("win", "podium", "top6", "top10")
_RALLY_STRATUM = "rally"


def _calibrate_markets(rally: RallyForecast, calibrator) -> dict:
    """Per-market probabilities, calibrated when a fitted model exists.

    Falls back to the raw Monte-Carlo probability when a market has no fitted
    model — so the output is always honest about what was calibrated."""
    raw_by_market = {
        "win": rally.markets.p_win,
        "podium": rally.markets.p_podium,
        "top6": rally.markets.p_top6,
        "top10": rally.markets.p_top10,
    }
    out: dict[str, dict[str, dict[str, float]]] = {}
    for market in _RAW_MARKET_KEYS:
        raw = raw_by_market[market]
        codes = list(raw.keys())
        raw_vals = np.array([raw[c] for c in codes], dtype=float)
        if calibrator is not None and calibrator.is_fitted(market, _RALLY_STRATUM):
            cal_vals = calibrator.transform(market, raw_vals, stratum=_RALLY_STRATUM)
        else:
            cal_vals = raw_vals
        # The win market is mutually exclusive — exactly one rally winner — so its
        # calibrated probabilities must sum to 1.0. Per-market isotonic calibration
        # + the probability floor over WRC's large field inflates the sum, so
        # renormalise win to a coherent market (order + the anti-collapse floor are
        # preserved; the top probability only shrinks). The top-k markets are
        # independent per-crew probabilities that legitimately sum to k, left as-is.
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


def probabilities_payload(fc: RoundForecast, calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    reason = (
        f"calibrated on {real_rounds} real rally result(s)"
        if applied
        else f"awaiting {config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds "
        f"({real_rounds} so far); showing raw Monte-Carlo probabilities"
    )
    return {
        "round": fc.round,
        "season": fc.season,
        "venueKey": fc.venue_key,
        "venueName": fc.venue_name,
        "surface": fc.surface,
        "surfaceColor": _surface_color(fc.surface),
        "calibration": {"applied": applied, "reason": reason},
        "rally": {
            "surface": fc.surface,
            "markets": _calibrate_markets(fc.rally, calibrator),
            "h2h": _h2h_subset(fc.rally),
            "method": "monte-carlo",
            "monteCarloSamples": fc.rally.n_samples,
            "temperature": fc.rally.temperature,
        },
    }


def _real_completed_rounds(source: WrcDataSource, year: int) -> list[int]:
    """Completed rounds backed by a real classified rally (all completed rounds in
    the committed WRC snapshot are real)."""
    return [
        r for r in range(1, config.COMPLETED_ROUNDS + 1) if _actual_map(source, year, r)
    ]


def build_calibrator(round_forecasts: dict[int, RoundForecast], source: WrcDataSource, year: int):
    """Fit a probability calibrator from the *real* completed rounds' markets.

    Reuses the leakage-safe forecasts already computed. Below
    ``config.MIN_REAL_ROUNDS_FOR_CALIBRATION`` it returns ``(None, count)`` so the
    site honestly reports calibration as not-yet-applied — the shared gate. WRC
    ships a full real corpus, so it fits."""
    real_rounds = _real_completed_rounds(source, year)
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)

    records: list[dict] = []
    for rnd in real_rounds:
        fc = round_forecasts[rnd]
        actual = _actual_map(source, year, rnd)
        recs = calibration.collect_history_from_rounds({rnd: fc.rally.markets}, {rnd: actual})
        for rec in recs:
            rec["stratum"] = _RALLY_STRATUM
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
            "Calibrated on real WRC rally results (one classification per round)."
            if applied
            else "Probability calibration turns on once "
            f"{config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds accrue "
            f"({real_rounds} so far)."
        ),
        "perMarket": per_market,
    }


# --------------------------------------------------------------------------- #
# Standings (drivers replayed from real results; manufacturers taken directly)
# --------------------------------------------------------------------------- #
def _driver_replay(source: WrcDataSource, year: int):
    """Per-driver cumulative real points after each completed round, plus wins /
    podiums. Uses each rally result's real awarded points (which include the Super
    Sunday + Power Stage bonuses), so the cumulative history reconciles exactly with
    the official season totals."""
    codes = [d["code"] for d in config.DRIVERS]
    hist: dict[str, list[float]] = {c: [] for c in codes}
    wins: dict[str, int] = {c: 0 for c in codes}
    podiums: dict[str, int] = {c: 0 for c in codes}
    cum: dict[str, float] = {c: 0.0 for c in codes}
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        by = {r.competitor: r for r in source.results(year, rnd)}
        for c in codes:
            r = by.get(c)
            if r is not None:
                cum[c] += float(r.points or 0.0)
                if r.position == 1:
                    wins[c] += 1
                if r.position is not None and r.position <= 3:
                    podiums[c] += 1
            hist[c].append(round(cum[c], 1))
    return hist, wins, podiums


def _standings_lists(source: WrcDataSource, year: int) -> tuple[list[dict], list[dict]]:
    """(driverStandings, manufacturerStandings). Drivers use the snapshot's official
    point totals + positions for display and the replay for wins/podiums and the
    per-round cumulative history the progression chart draws. Manufacturers are the
    official constructors'-championship entries, taken directly from the snapshot."""
    hist, wins, podiums = _driver_replay(source, year)
    snap = config.load_snapshot(year)
    official_drivers = snap.get("driverStandings") if snap.get("season") == year else None
    official_manufacturers = (
        snap.get("manufacturerStandings") if snap.get("season") == year else None
    )

    driver_rows: list[dict] = []
    source_rows = official_drivers or [
        {"code": c, "points": h[-1] if h else 0.0} for c, h in hist.items()
    ]
    if not official_drivers:  # fallback: rank purely by replayed points
        source_rows = sorted(source_rows, key=lambda d: -float(d["points"]))
    for i, d in enumerate(source_rows, start=1):
        code = d["code"]
        team = config.TEAM_OF.get(code, d.get("manufacturer") or "Privateer")
        driver_rows.append(
            {
                "position": d.get("position", i),
                "code": code,
                "name": config.DRIVER_NAME.get(code, d.get("name", code)),
                "nationality": config.DRIVER_NATION.get(code, d.get("nationality")),
                "team": team,
                "teamColor": _MAN_COLORS.get(team, _NEUTRAL),
                "points": float(d["points"]),
                "wins": wins.get(code, 0),
                "podiums": podiums.get(code, 0),
                "pointsHistory": hist.get(code, []),
            }
        )

    manufacturer_rows: list[dict] = []
    for i, t in enumerate(official_manufacturers or [], start=1):
        name = t["name"]
        manufacturer_rows.append(
            {
                "position": i,
                "team": name,
                "teamColor": _manufacturer_color(name),
                "points": float(t["points"]),
            }
        )
    return driver_rows, manufacturer_rows


def _current_points(driver_rows: list[dict]) -> dict[str, float]:
    return {d["code"]: float(d["points"]) for d in driver_rows}


# --------------------------------------------------------------------------- #
# Championship (drivers' title, can-still-win math)
# --------------------------------------------------------------------------- #
def _championship(source: WrcDataSource, year: int, current_points: dict[str, float]) -> list[dict]:
    skill = model.estimate_skill(source, year, current_round=config.COMPLETED_ROUNDS + 1)
    remaining = config.TOTAL_ROUNDS - config.COMPLETED_ROUNDS
    points = {c: float(current_points.get(c, 0.0)) for c in skill}
    title = model.project_championship_wrc(points, skill, remaining_rounds=remaining)
    leader_points = max((t.current_points for t in title), default=0.0)
    ceiling = max(remaining, 0) * _MAX_POINTS_PER_ROUND
    out: list[dict] = []
    for t in title:
        max_attainable = t.current_points + ceiling
        out.append(
            {
                "code": t.key,
                "name": config.DRIVER_NAME.get(t.key, t.key),
                "team": config.TEAM_OF.get(t.key, "Privateer"),
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
# Season accuracy (leakage-safe per-round predictions vs actual)
# --------------------------------------------------------------------------- #
def _season_accuracy(
    round_forecasts: dict[int, RoundForecast], source: WrcDataSource, year: int
) -> dict:
    scored = 0
    pos_errors: list[float] = []
    podium_hits = 0
    winner_hits = 0
    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        fc = round_forecasts[rnd]
        actual = _actual_map(source, year, rnd)
        if not actual:
            continue
        predicted = {code: i for i, code in enumerate(fc.rally.order, start=1)}
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
    years are discovered by scanning ``<out_dir>/seasons/`` (same schema as F1)."""
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
# Top-level season summary (wrc.json)
# --------------------------------------------------------------------------- #
def build_payload(
    round_forecasts: dict[int, RoundForecast],
    source: WrcDataSource,
    year: int,
    next_round: int | None,
) -> dict:
    completed = source.completed_rounds(year)
    n_completed = len(completed)
    driver_rows, manufacturer_rows = _standings_lists(source, year)
    current_points = _current_points(driver_rows)

    prediction = None
    if next_round is not None:
        fc = round_forecasts[next_round]
        rally = fc.rally
        prediction = {
            "season": fc.season,
            "round": fc.round,
            "venueKey": fc.venue_key,
            "venueName": fc.venue_name,
            "surface": fc.surface,
            "surfaceColor": _surface_color(fc.surface),
            "phase": "pre",  # rally has no qualifying, so the forecast is always pre-event
            "rally": [
                {
                    "position": i,
                    "code": c,
                    "name": config.DRIVER_NAME.get(c, c),
                    "team": config.TEAM_OF.get(c, "Privateer"),
                    "pWin": round(rally.markets.p_win.get(c, 0.0), 4),
                    "pPodium": round(rally.markets.p_podium.get(c, 0.0), 4),
                }
                for i, c in enumerate(rally.order, start=1)
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
                "surface": config.surface_for_round(i),
                "surfaceColor": _surface_color(config.surface_for_round(i)),
                "date": meta.get(i, {}).get("date", ""),
                "completed": i in completed,
                "dataSource": source.provenance(year, i) if i in completed else None,
            }
            for i, v in enumerate(config.CALENDAR, start=1)
        ],
        "driverStandings": driver_rows,
        "manufacturerStandings": manufacturer_rows,
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

    source = WrcDataSource()
    year = config.SEASON
    next_round = _next_round(source, year)

    # Forecast every round once, leakage-safe (each round's pace reads only strictly
    # prior rounds + prior seasons; the ensemble form prior is leakage-safe too).
    round_forecasts: dict[int, RoundForecast] = {}
    for rnd in range(1, len(config.CALENDAR) + 1):
        round_forecasts[rnd] = model.forecast_round(source, year, rnd)

    # Honest calibration gate (fit from the real completed rounds' markets).
    calibrator, real_rounds = build_calibrator(round_forecasts, source, year)

    for rnd, fc in round_forecasts.items():
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

    payload = build_payload(round_forecasts, source, year, next_round)
    path = out_dir / "wrc.json"
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
