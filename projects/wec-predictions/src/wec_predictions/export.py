"""Generate the FIA WEC website's JSON from the model + committed snapshots.

The website is a static export, so this module is the single producer of its data
contract under ``public/data/``. It mirrors the suite's fan-out shape (so the site
shares components with the other series) but every payload is **keyed by class**,
because endurance is scored per class (Hypercar / LMP2 / LMGT3 / the GTE classes
in older seasons):

    public/data/
      wec.json                     season summary: calendar, per-class standings,
                                   per-class championship, per-class next-round
                                   prediction, season accuracy
      rounds/round_NN.json         per-round, per-class predicted + actual order
      probabilities/round_NN.json  per-round, per-class markets + calibration
      calibration_summary.json     honest calibration status
      seasons.json                 multi-season index

Every forecast is leakage-safe (each round's pace uses only strictly-prior rounds).
Only classes actually racing at a round are forecast (Le Mans adds LMP2; regular
rounds don't). Standings and championship cover the **regular-season classes**
only — the classes that contest the full-season title.

Run:  python -m wec_predictions.export   [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from motorsport_core import calibration, eval as core_eval

from . import config, model
from .datasource import WecDataSource
from .model import ClassForecast, RoundForecast

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# A full WEC season has run 6-8 rounds in recent years; when the live season's
# remaining calendar isn't yet in the archive we project the title assuming it
# reaches this many rounds (documented in the payload's ``basis``).
EXPECTED_TOTAL_ROUNDS = 8
H2H_TOP_N = 10
_NEUTRAL = "#8A8A8A"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _manuf_color(code: str) -> str:
    m = config.MANUF_OF.get(code, "")
    for t in config.TEAMS:
        if t.name == m:
            return t.color or _NEUTRAL
    return _NEUTRAL


def _entry_row_meta(code: str) -> dict:
    e = config.ENTRY_META.get(code, {})
    return {
        "code": code,
        "number": e.get("number", ""),
        "team": e.get("team", ""),
        "manufacturer": e.get("manufacturer", ""),
        "vehicle": e.get("vehicle", ""),
        "drivers": e.get("drivers", []),
        "teamColor": _manuf_color(code),
    }


# --------------------------------------------------------------------------- #
# Class helpers
# --------------------------------------------------------------------------- #
def _class_meta(cls: str) -> dict:
    return {"key": cls, "label": config.class_label(cls), "color": config.class_color(cls)}


def _regular_classes(source: WecDataSource, year: int) -> list[str]:
    """Classes that contest the full-season title (exclude Le-Mans-only classes)."""
    nxt = config.next_round()
    return source.classes_for_round(year, nxt)


# --------------------------------------------------------------------------- #
# Per-class standings replay (cumulative points after each completed round)
# --------------------------------------------------------------------------- #
def _class_standings(source: WecDataSource, year: int, cls: str) -> list[dict]:
    completed = sorted(source.completed_rounds(year))
    points: dict[str, float] = {}
    wins: dict[str, int] = {}
    podiums: dict[str, int] = {}
    history: dict[str, list[float]] = {}
    seen: list[str] = []
    for rnd in completed:
        res = source.class_results(year, rnd, cls) or []
        for r in res:
            if r.competitor not in seen:
                seen.append(r.competitor)
            pts = config.FEATURE_POINTS.get(r.position or 0, 0)
            points[r.competitor] = points.get(r.competitor, 0.0) + pts
            if r.position == 1:
                wins[r.competitor] = wins.get(r.competitor, 0) + 1
            if r.position and r.position <= 3:
                podiums[r.competitor] = podiums.get(r.competitor, 0) + 1
        for code in seen:
            history.setdefault(code, []).append(points.get(code, 0.0))
    rows = []
    for i, (code, pts) in enumerate(sorted(points.items(), key=lambda kv: -kv[1]), start=1):
        rows.append({
            "position": i,
            **_entry_row_meta(code),
            "points": float(pts),
            "wins": wins.get(code, 0),
            "podiums": podiums.get(code, 0),
            "pointsHistory": history.get(code, []),
        })
    return rows


# --------------------------------------------------------------------------- #
# Per-class championship projection (assumed remaining rounds)
# --------------------------------------------------------------------------- #
def _class_championship(source: WecDataSource, year: int, cls: str,
                        standings: list[dict], *, n_samples: int = 4000, seed: int = 7) -> dict:
    completed = len(source.completed_rounds(year))
    remaining = max(0, EXPECTED_TOTAL_ROUNDS - completed)
    current = {r["code"]: r["points"] for r in standings}
    field = [r["code"] for r in standings]
    if not field:
        return {"basis": "no results yet", "remainingRounds": remaining, "entries": []}

    skill = model.estimate_class_skill(source, year, config.next_round(), cls, field)
    idx = {c: i for i, c in enumerate(field)}
    base = np.array([current.get(c, 0.0) for c in field], dtype=float)
    sim = np.tile(base, (n_samples, 1))
    if remaining > 0 and skill:
        orders = calibration.sample_finishing_orders(
            skill, n_samples=n_samples * remaining, seed=seed)
        cur = 0
        for _ in range(remaining):
            for s in range(n_samples):
                for pos, c in enumerate(orders[cur], start=1):
                    sim[s, idx[c]] += config.FEATURE_POINTS.get(pos, 0)
                cur += 1
    win_counts = np.bincount(np.argmax(sim, axis=1), minlength=len(field))
    leader_pts = max(current.values()) if current else 0.0
    ceiling = remaining * max(config.FEATURE_POINTS.values())
    entries = []
    for c in field:
        max_attainable = current.get(c, 0.0) + ceiling
        entries.append({
            **_entry_row_meta(c),
            "pTitle": round(float(win_counts[idx[c]] / n_samples), 4),
            "currentPoints": current.get(c, 0.0),
            "projMean": round(float(sim[:, idx[c]].mean()), 2),
            "projP10": round(float(np.percentile(sim[:, idx[c]], 10)), 1),
            "projP90": round(float(np.percentile(sim[:, idx[c]], 90)), 1),
            "maxAttainable": max_attainable,
            "canStillWin": max_attainable >= leader_pts,
        })
    entries.sort(key=lambda e: -e["pTitle"])
    basis = (f"assuming a full {EXPECTED_TOTAL_ROUNDS}-round season "
             f"({remaining} rounds remaining)" if remaining > 0
             else "season complete in the archive; standings are final")
    return {"basis": basis, "remainingRounds": remaining, "entries": entries}


# --------------------------------------------------------------------------- #
# Per-round detail
# --------------------------------------------------------------------------- #
def _actual_class(source: WecDataSource, year: int, rnd: int, cls: str) -> dict[str, int]:
    res = source.class_results(year, rnd, cls) or []
    return {r.competitor: r.position for r in res if r.position is not None}


def _classification(cf: ClassForecast, actual: dict[str, int]) -> list[dict]:
    m = cf.markets
    rows = []
    for pos, code in enumerate(cf.order, start=1):
        rows.append({
            "position": pos,
            **_entry_row_meta(code),
            "predictedValue": round(cf.score.get(code, 0.0), 3),
            "pWin": round(m.p_win.get(code, 0.0), 4),
            "pPodium": round(m.p_podium.get(code, 0.0), 4),
            "pTop6": round(m.p_top6.get(code, 0.0), 4),
            "pTop10": round(m.p_top10.get(code, 0.0), 4),
            "meanFinish": round(cf.mean_finish[code], 2),
            "finishRangeLow": cf.range_low[code],
            "finishRangeHigh": cf.range_high[code],
            "confidence": cf.confidence.get(code, "Medium"),
            "actualPosition": actual.get(code),
        })
    return rows


def _class_block(cf: ClassForecast, source: WecDataSource, year: int, rnd: int,
                 completed: bool) -> dict:
    actual = _actual_class(source, year, rnd, cf.cls) if completed else {}
    block = {
        **_class_meta(cf.cls),
        "classification": _classification(cf, actual),
    }
    if completed and actual:
        block["actualResults"] = [
            {"position": pos, "code": code}
            for code, pos in sorted(actual.items(), key=lambda kv: kv[1])
        ]
        predicted = {code: i for i, code in enumerate(cf.order, start=1)}
        block["accuracy"] = core_eval.score_round(predicted, actual)
    return block


def round_payload(fc: RoundForecast, source: WecDataSource, completed: bool) -> dict:
    return {
        "round": fc.round,
        "season": fc.season,
        "place": fc.place,
        "country": fc.country,
        "event": fc.event,
        "completed": completed,
        "dataSource": source.snapshot.provenance(fc.season, fc.round) if completed else None,
        "classes": [_class_block(cf, source, fc.season, fc.round, completed) for cf in fc.classes],
    }


# --------------------------------------------------------------------------- #
# Per-round probabilities (with per-class win-market renormalisation)
# --------------------------------------------------------------------------- #
_RAW_MARKET_KEYS = ("win", "podium", "top6", "top10")


def _calibrate_markets(cf: ClassForecast, calibrator) -> dict:
    raw_by_market = {
        "win": cf.markets.p_win, "podium": cf.markets.p_podium,
        "top6": cf.markets.p_top6, "top10": cf.markets.p_top10,
    }
    out: dict[str, dict[str, dict[str, float]]] = {}
    for market in _RAW_MARKET_KEYS:
        raw = raw_by_market[market]
        codes = list(raw.keys())
        raw_vals = np.array([raw[c] for c in codes], dtype=float)
        if calibrator is not None and calibrator.is_fitted(market, cf.cls):
            cal_vals = calibrator.transform(market, raw_vals, stratum=cf.cls)
        else:
            cal_vals = raw_vals
        # Per-competitor calibration does not preserve the simplex. Each entry is
        # mapped independently, so the market stops summing to the size of the set
        # it describes. This was handled here for `win` alone, on the reasoning
        # that the top-k markets "legitimately sum to k" — true of what they MEAN,
        # but not of what calibration leaves behind. All four markets are
        # renormalised together after the loop, by the shared water-fill.
        out[market] = {
            c: {"probability": float(cal_vals[i]),
                "rawProbability": round(float(raw_vals[i]), 4)}
            for i, c in enumerate(codes)
        }
    return calibration.renormalize_market_struct(out, digits=4)


def _h2h_subset(cf: ClassForecast) -> dict:
    top = list(cf.order[:H2H_TOP_N])
    h2h = cf.markets.h2h
    return {a: {b: round(h2h[a][b], 4) for b in top if b in h2h.get(a, {})}
            for a in top if a in h2h}


def probabilities_payload(fc: RoundForecast, calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    reason = (f"calibrated on {real_rounds} real round(s)" if applied
              else f"awaiting {config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds "
                   f"({real_rounds} so far); showing raw Monte-Carlo probabilities")
    return {
        "round": fc.round,
        "season": fc.season,
        "place": fc.place,
        "calibration": {"applied": applied, "reason": reason},
        "classes": [
            {
                **_class_meta(cf.cls),
                "markets": _calibrate_markets(cf, calibrator),
                "h2h": _h2h_subset(cf),
                "method": "monte-carlo",
                "monteCarloSamples": cf.n_samples,
                "temperature": cf.temperature,
            }
            for cf in fc.classes
        ],
    }


def build_calibrator(round_forecasts: dict[int, RoundForecast], source: WecDataSource, year: int):
    real_rounds = sorted(source.completed_rounds(year))
    if len(real_rounds) < config.MIN_REAL_ROUNDS_FOR_CALIBRATION:
        return None, len(real_rounds)
    records: list[dict] = []
    for rnd in real_rounds:
        fc = round_forecasts.get(rnd)
        if not fc:
            continue
        for cf in fc.classes:
            actual = _actual_class(source, year, rnd, cf.cls)
            if not actual:
                continue
            recs = calibration.collect_history_from_rounds({rnd: cf.markets}, {rnd: actual})
            for rec in recs:
                rec["stratum"] = cf.cls
            records.extend(recs)
    calibrator = calibration.StratifiedProbabilityCalibrator().fit_from_history(records)
    return (calibrator if calibrator.is_fitted() else None), len(real_rounds)


def _calibration_summary(calibrator, real_rounds: int) -> dict:
    applied = calibrator is not None
    return {
        "generatedAt": _now_iso(),
        "applied": applied,
        "trainingRounds": real_rounds,
        "dataLimitation": (
            "Calibrated on real WEC results, per class stratum." if applied
            else "Probability calibration turns on once "
                 f"{config.MIN_REAL_ROUNDS_FOR_CALIBRATION} real rounds accrue "
                 f"({real_rounds} so far)."),
    }


# --------------------------------------------------------------------------- #
# Season accuracy (per class + overall), leakage-safe predictions vs actual
# --------------------------------------------------------------------------- #
def _season_accuracy(round_forecasts: dict[int, RoundForecast], source: WecDataSource,
                     year: int) -> dict:
    by_class: dict[str, dict] = {}
    all_pos: list[float] = []
    all_pod = 0
    all_win = 0
    all_scored = 0
    for rnd in sorted(source.completed_rounds(year)):
        fc = round_forecasts.get(rnd)
        if not fc:
            continue
        for cf in fc.classes:
            actual = _actual_class(source, year, rnd, cf.cls)
            if not actual:
                continue
            predicted = {code: i for i, code in enumerate(cf.order, start=1)}
            score = core_eval.score_round(predicted, actual)
            if score.get("n", 0) == 0:
                continue
            b = by_class.setdefault(cf.cls, {"pos": [], "pod": 0, "win": 0, "scored": 0})
            if score.get("mean_position_error") is not None:
                b["pos"].append(score["mean_position_error"])
                all_pos.append(score["mean_position_error"])
            b["pod"] += score.get("podium_hits", 0)
            b["win"] += 1 if score.get("winner_hit") else 0
            b["scored"] += 1
            all_pod += score.get("podium_hits", 0)
            all_win += 1 if score.get("winner_hit") else 0
            all_scored += 1
    per_class = {
        cls: {
            "roundsScored": b["scored"],
            "meanPositionError": round(sum(b["pos"]) / len(b["pos"]), 3) if b["pos"] else None,
            "podiumHitRate": round(b["pod"] / (b["scored"] * 3), 4) if b["scored"] else None,
            "winnerHitRate": round(b["win"] / b["scored"], 4) if b["scored"] else None,
        }
        for cls, b in by_class.items()
    }
    overall = {
        "roundsScored": all_scored,
        "meanPositionError": round(sum(all_pos) / len(all_pos), 3) if all_pos else None,
        "podiumHitRate": round(all_pod / (all_scored * 3), 4) if all_scored else None,
        "winnerHitRate": round(all_win / all_scored, 4) if all_scored else None,
    }
    return {"overall": overall, "byClass": per_class}


# --------------------------------------------------------------------------- #
# Multi-season index
# --------------------------------------------------------------------------- #
def write_seasons_index(out_dir: Path, current: int) -> dict:
    seasons_dir = out_dir / "seasons"
    archived = sorted(
        int(p.name) for p in (seasons_dir.iterdir() if seasons_dir.is_dir() else [])
        if p.is_dir() and p.name.isdigit() and int(p.name) != current)
    available = sorted(set(archived) | {current})
    index = {
        "current": current, "available": available, "archived": archived,
        "lastUpdated": _now_iso(),
        "seasons": [
            {"year": y, "isCurrent": y == current,
             "path": "" if y == current else f"seasons/{y}", "label": str(y)}
            for y in available
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seasons.json").write_text(json.dumps(index, indent=2) + "\n")
    return index


# --------------------------------------------------------------------------- #
# Top-level season summary (wec.json)
# --------------------------------------------------------------------------- #
def build_payload(round_forecasts: dict[int, RoundForecast], source: WecDataSource,
                  year: int, next_round: int | None) -> dict:
    completed = sorted(source.completed_rounds(year))
    reg_classes = _regular_classes(source, year)

    standings = {cls: _class_standings(source, year, cls) for cls in reg_classes}
    championship = {
        cls: _class_championship(source, year, cls, standings[cls]) for cls in reg_classes
    }

    prediction = None
    if next_round is not None and next_round in round_forecasts:
        fc = round_forecasts[next_round]
        prediction = {
            "season": fc.season, "round": fc.round, "place": fc.place, "country": fc.country,
            "event": fc.event,
            "classes": [
                {
                    **_class_meta(cf.cls),
                    "race": [
                        {"position": i, **_entry_row_meta(c),
                         "pWin": round(cf.markets.p_win.get(c, 0.0), 4),
                         "pPodium": round(cf.markets.p_podium.get(c, 0.0), 4)}
                        for i, c in enumerate(cf.order, start=1)
                    ],
                }
                for cf in fc.classes
            ],
        }

    return {
        "sport": config.SPORT,
        "season": year,
        "generatedAt": _now_iso(),
        "completedRounds": len(completed),
        "lastUpdatedRound": max(completed) if completed else 0,
        "totalRounds": config.TOTAL_ROUNDS,
        "classes": [_class_meta(c) for c in reg_classes],
        "calendar": [
            {
                "round": e["round"], "key": e.get("venue", ""), "name": e.get("event", ""),
                "place": e.get("place", ""), "country": e.get("country", ""),
                "completed": e.get("completed", False),
                "isLeMans": "le mans" in (e.get("event", "").lower()),
                "dataSource": source.snapshot.provenance(year, e["round"]) if e.get("completed") else None,
            }
            for e in config.FULL_CALENDAR
        ],
        "standings": standings,
        "championship": championship,
        "seasonAccuracy": _season_accuracy(round_forecasts, source, year),
        "nextPrediction": prediction,
    }


# --------------------------------------------------------------------------- #
def out_dir_for_season(year: int, base: Path = DEFAULT_OUT) -> Path:
    return base if int(year) == int(config.SEASON) else base / "seasons" / str(year)


def write(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rounds").mkdir(parents=True, exist_ok=True)
    (out_dir / "probabilities").mkdir(parents=True, exist_ok=True)

    source = WecDataSource()
    year = config.SEASON
    completed = sorted(source.completed_rounds(year))
    next_round = config.next_round()
    rounds_to_emit = sorted(set(completed) | ({next_round} if next_round else set()))

    round_forecasts: dict[int, RoundForecast] = {}
    for rnd in rounds_to_emit:
        round_forecasts[rnd] = model.forecast_round(source, year, rnd)

    calibrator, real_rounds = build_calibrator(round_forecasts, source, year)

    for rnd, fc in round_forecasts.items():
        is_completed = rnd in completed
        (out_dir / "rounds" / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(round_payload(fc, source, is_completed), indent=2) + "\n")
        (out_dir / "probabilities" / f"round_{_pad2(rnd)}.json").write_text(
            json.dumps(probabilities_payload(fc, calibrator, real_rounds), indent=2) + "\n")

    (out_dir / "calibration_summary.json").write_text(
        json.dumps(_calibration_summary(calibrator, real_rounds), indent=2) + "\n")

    payload = build_payload(round_forecasts, source, year, next_round)
    path = out_dir / "wec.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    write_seasons_index(out_dir, current=year)
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    path = write(args.out)
    print(f"Wrote {path} + per-round files under {path.parent}/rounds and /probabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
