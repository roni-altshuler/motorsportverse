"""Forward-time evaluation for the FIA WEC — leakage-safe, per class.

**This is the headline honesty surface for the WEC model.** Endurance is
multi-class (Hypercar / LMP2 / LMGT3 / the GTE classes in older seasons), so a
round is not one race but one *per class*. For every completed round and every
class that ran it, we re-run the model with **only prior-round data** and score
its within-class markets against the actual within-class classification, then
publish the same numbers for two trivial baselines so "is the model beating the
obvious predictor?" is a single read:

* **last-race order** — predict the class order = that class's previous round's
  finishing order (falls back to the prior season's final round for the opener).
* **season-form order** — predict the class order = the average within-class
  finishing position over the prior rounds this season (cross-season fallback).

All three run through the SAME Plackett-Luce sampler at the same temperature, so
only the *signal* differs — the Brier / log-loss comparison is apples-to-apples
(this mirrors ``wec_validate`` / the never-ship-worse gate). Scoring is over the
**classified** entries in each class (retirements are unranked). Metrics reuse
:mod:`motorsport_core.eval` (``score_round`` bundle + ``brier_score`` / ``log_loss``).

Outputs (under ``website/public/data/``):
    forward_eval/round_NN.json  per-round, per-class model + both baselines
    forward_eval/season.json    season roll-up: overall + per-class model vs
                                baselines, plus a walk-forward summary
    model_health.json           the folded forward-eval headline + feature drift

Everything is leakage-safe: round R's own results never inform round R's forecast.

Run:  python -m wec_predictions.forward_eval --season 2026 [--allow-empty] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from motorsport_core import calibration, drift, eval as core_eval

from . import config, model
from .datasource import WecDataSource
from .model import _zscores

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "website" / "public" / "data"

# Same sampler settings for the model and both baselines: only the pace signal
# differs, so the Brier comparison isolates the signal (matches wec_validate).
NS = config.DEFAULT_SAMPLES
T = config.BASE_TEMPERATURE

METHODS = ("model", "lastRace", "seasonForm")
_METRIC_KEYS = ("winBrier", "podiumBrier", "winLogLoss", "podiumLogLoss")

# Exported round-file columns model_health watches for distribution drift.
_FEATURE_COLUMNS = ("predictedValue", "pWin", "pPodium", "meanFinish", "finishRangeHigh")
_DRIFT_WINDOW = 3


def _pad2(n: int) -> str:
    return f"{n:02d}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _class_meta(cls: str) -> dict:
    return {"class": cls, "label": config.class_label(cls), "color": config.class_color(cls)}


def _round_meta(year: int, rnd: int) -> dict:
    for e in config.load_snapshot(year).get("fullCalendar") or []:
        if int(e.get("round", -1)) == rnd:
            return e
    return {"round": rnd, "place": f"Round {rnd}", "country": "", "event": f"Round {rnd}"}


# --------------------------------------------------------------------------- #
# Baseline pace signals (productionised from the validation harness)
# --------------------------------------------------------------------------- #
def _pace_from_signal(signal: dict[str, float]) -> dict[str, float]:
    """Map a per-entry merit signal to the same pace scale the model emits, so a
    baseline is scored with the identical Plackett-Luce spread — only the ranking
    signal differs."""
    z = _zscores(signal)
    return {c: config.PACE_BASE - config.PACE_SPREAD * z.get(c, 0.0) for c in signal}


def _lastrace_signal(source: WecDataSource, year: int, rnd: int, cls: str,
                     field: list[str]) -> dict[str, float]:
    """Previous within-class order (negated position); prior-season fallback for R1."""
    prior = [r for r in source.completed_rounds(year) if r < rnd]
    pos: dict[str, int] = {}
    if prior:
        res = source.class_results(year, max(prior), cls)
        pos = {r.competitor: r.position for r in res} if res else {}
    if not pos:
        for y in reversed([s for s in config.HISTORY_SEASONS if s < year]):
            rounds = source.completed_rounds(y)
            if rounds:
                res = source.class_results(y, max(rounds), cls)
                if res:
                    pos = {r.competitor: r.position for r in res}
                    break
    worst = (max(pos.values()) + 1) if pos else 1
    return {c: -float(pos.get(c, worst)) for c in field}


def _form_signal(source: WecDataSource, year: int, rnd: int, cls: str,
                 field: list[str]) -> dict[str, float]:
    """Average within-class finish over prior rounds this season (negated)."""
    avg, _counts = source.prior_form(year, rnd, cls)
    fm = (sum(avg.values()) / len(avg)) if avg else 0.0
    return {c: -avg.get(c, fm) for c in field}


# --------------------------------------------------------------------------- #
# Scoring helpers
# --------------------------------------------------------------------------- #
def _order_positions(order: list[str]) -> dict[str, int]:
    return {code: i for i, code in enumerate(order, start=1)}


def _score_order(order: list[str], actual: dict[str, int]) -> dict:
    return core_eval.score_round(_order_positions(order), actual)


def _market_scores(p_win, p_podium, actual: dict[str, int]) -> dict:
    """Per-market probability quality (Brier + log-loss) over the classified field."""
    if not actual:
        return {}
    winner = min(actual, key=actual.get)
    win_out = {c: 1.0 if c == winner else 0.0 for c in actual}
    podium = {c for c, p in actual.items() if p <= 3}
    pod_out = {c: 1.0 if c in podium else 0.0 for c in actual}
    out: dict[str, dict] = {}
    for name, probs, outcomes in (("win", p_win, win_out), ("podium", p_podium, pod_out)):
        brier = core_eval.brier_score(probs, outcomes)
        ll = core_eval.log_loss(probs, outcomes)
        out[name] = {
            "brier": round(brier, 6) if brier is not None else None,
            "logLoss": round(ll, 6) if ll is not None else None,
        }
    return out


def _baseline_block(source: WecDataSource, year: int, rnd: int, cls: str,
                    field: list[str], actual: dict[str, int],
                    signal: dict[str, float]) -> dict:
    pace = _pace_from_signal(signal)
    order = sorted(field, key=lambda c: pace.get(c, config.PACE_BASE))
    mkts = calibration.plackett_luce_probabilities(pace, n_samples=NS, temperature=T)
    return {
        "score": _score_order(order, actual),
        "markets": _market_scores(mkts.p_win, mkts.p_podium, actual),
    }


# --------------------------------------------------------------------------- #
# Per-round, per-class evaluation
# --------------------------------------------------------------------------- #
def evaluate_season(source: WecDataSource, year: int) -> list[dict]:
    """Score every completed round, per class, with leakage-safe replays."""
    rounds: list[dict] = []
    for rnd in sorted(source.completed_rounds(year)):
        class_blocks: list[dict] = []
        for cls in source.classes_for_round(year, rnd):
            res = source.class_results(year, rnd, cls)
            if not res or len(res) < 4:
                continue
            field = [r.competitor for r in res]
            actual = {r.competitor: r.position for r in res}
            fc = model.forecast_class(source, year, rnd, cls, n_samples=NS, field=field)
            if fc is None:
                continue
            class_blocks.append(
                {
                    **_class_meta(cls),
                    "field": len(field),
                    "score": _score_order(fc.order, actual),
                    "markets": _market_scores(fc.markets.p_win, fc.markets.p_podium, actual),
                    "baselines": {
                        "lastRace": _baseline_block(
                            source, year, rnd, cls, field, actual,
                            _lastrace_signal(source, year, rnd, cls, field)),
                        "seasonForm": _baseline_block(
                            source, year, rnd, cls, field, actual,
                            _form_signal(source, year, rnd, cls, field)),
                    },
                }
            )
        if class_blocks:
            meta = _round_meta(year, rnd)
            rounds.append(
                {
                    "round": rnd,
                    "season": year,
                    "place": meta.get("place", f"Round {rnd}"),
                    "country": meta.get("country") or None,
                    "event": meta.get("event", f"Round {rnd}"),
                    "classes": class_blocks,
                }
            )
    return rounds


# --------------------------------------------------------------------------- #
# Aggregation: overall + per class, model vs both baselines
# --------------------------------------------------------------------------- #
def _markets_of(block: dict, method: str) -> dict:
    if method == "model":
        return block.get("markets") or {}
    return (block.get("baselines", {}).get(method) or {}).get("markets") or {}


def _metric_values(markets: dict) -> dict[str, float | None]:
    win = markets.get("win") or {}
    pod = markets.get("podium") or {}
    return {
        "winBrier": win.get("brier"),
        "podiumBrier": pod.get("brier"),
        "winLogLoss": win.get("logLoss"),
        "podiumLogLoss": pod.get("logLoss"),
    }


def _mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def _summarise(blocks: list[dict]) -> dict:
    """{method: {metric: mean}} over a list of class-round blocks + roundsScored."""
    acc = {m: {k: [] for k in _METRIC_KEYS} for m in METHODS}
    for block in blocks:
        for m in METHODS:
            mv = _metric_values(_markets_of(block, m))
            for k in _METRIC_KEYS:
                if mv[k] is not None:
                    acc[m][k].append(mv[k])
    out = {"classRoundsScored": len(blocks)}
    for m in METHODS:
        out[m] = {k: _mean(acc[m][k]) for k in _METRIC_KEYS}
    return out


def _aggregate(rounds: list[dict]) -> dict:
    all_blocks = [b for r in rounds for b in r["classes"]]
    by_class: dict[str, list[dict]] = {}
    for b in all_blocks:
        by_class.setdefault(b["class"], []).append(b)
    return {
        "overall": _summarise(all_blocks),
        "byClass": {cls: _summarise(blocks) for cls, blocks in by_class.items()},
    }


def _verdict(summary: dict) -> dict:
    """Honest aggregate win+podium-Brier deltas, model minus each baseline.

    Negative delta = the model is better; ``notWorse`` is a directional gate with a
    tiny Monte-Carlo tolerance. Raw numbers for all methods are always published
    alongside — no cherry-picking.
    """
    def agg(method: str) -> float | None:
        w = summary[method]["winBrier"]
        p = summary[method]["podiumBrier"]
        return round(w + p, 6) if (w is not None and p is not None) else None

    model_agg = agg("model")
    out: dict = {"modelWinPodiumBrier": model_agg, "vs": {}}
    tol = 0.01
    for base in ("lastRace", "seasonForm"):
        base_agg = agg(base)
        delta = (round(model_agg - base_agg, 6)
                 if (model_agg is not None and base_agg is not None) else None)
        out["vs"][base] = {
            "baselineWinPodiumBrier": base_agg,
            "delta": delta,
            "notWorse": (delta is not None and delta <= tol),
        }
    return out


# --------------------------------------------------------------------------- #
# Walk-forward summary (per class + overall, model vs baselines)
# --------------------------------------------------------------------------- #
def _flatten(score: dict | None, markets: dict | None) -> dict[str, float]:
    """Numeric per-round metric view for walk_forward_summary."""
    out: dict[str, float] = {}
    for key, val in (score or {}).items():
        if key == "n":
            continue
        if key == "winner_hit":
            out["winnerHit"] = 1.0 if val else 0.0
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        out[key] = float(val)
    for market, metrics in (markets or {}).items():
        for name, val in (metrics or {}).items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[f"{market}{name[0].upper()}{name[1:]}"] = float(val)
    return out


def _wf_rows(blocks: list[dict], method: str) -> list[dict]:
    rows = []
    for b in blocks:
        if method == "model":
            rows.append(_flatten(b.get("score"), b.get("markets")))
        else:
            sub = b.get("baselines", {}).get(method)
            if sub:
                rows.append(_flatten(sub.get("score"), sub.get("markets")))
    return rows


def _wf_summary(blocks: list[dict]) -> dict:
    return {
        "model": core_eval.walk_forward_summary(_wf_rows(blocks, "model")),
        "baselines": {
            "lastRace": core_eval.walk_forward_summary(_wf_rows(blocks, "lastRace")),
            "seasonForm": core_eval.walk_forward_summary(_wf_rows(blocks, "seasonForm")),
        },
    }


def build_walk_forward(rounds: list[dict]) -> dict:
    all_blocks = [b for r in rounds for b in r["classes"]]
    by_class: dict[str, list[dict]] = {}
    for b in all_blocks:
        by_class.setdefault(b["class"], []).append(b)
    return {
        "overall": _wf_summary(all_blocks),
        "byClass": {cls: _wf_summary(blocks) for cls, blocks in by_class.items()},
    }


# --------------------------------------------------------------------------- #
# Season summary
# --------------------------------------------------------------------------- #
def _season_summary(year: int, rounds: list[dict]) -> dict:
    aggregate = _aggregate(rounds)
    # Positional headline (over every class-round the model scored).
    all_blocks = [b for r in rounds for b in r["classes"]]
    scored = [b for b in all_blocks if b["score"].get("n", 0) > 0]
    pos = [b["score"]["mean_position_error"] for b in scored
           if b["score"].get("mean_position_error") is not None]
    winner_hits = sum(1 for b in scored if b["score"].get("winner_hit"))
    podium_hits = sum(b["score"].get("podium_hits", 0) for b in scored)
    return {
        "season": year,
        "roundsScored": len(rounds),
        "classRoundsScored": len(all_blocks),
        "generatedAt": _utc_now_iso(),
        "classifiedOnly": True,
        "meanPositionError": round(sum(pos) / len(pos), 4) if pos else None,
        "winnerHitRate": round(winner_hits / len(scored), 4) if scored else None,
        "podiumHitRate": round(podium_hits / (len(scored) * 3), 4) if scored else None,
        "overall": aggregate["overall"],
        "byClass": aggregate["byClass"],
        "modelVsBaselines": _verdict(aggregate["overall"]),
        "walkForward": build_walk_forward(rounds),
    }


# --------------------------------------------------------------------------- #
# model_health.json — folded forward-eval headline + feature drift
# --------------------------------------------------------------------------- #
def _overall_round_win_brier(round_entry: dict) -> float | None:
    vals = [b["markets"].get("win", {}).get("brier")
            for b in round_entry["classes"] if b.get("markets")]
    return _mean([v for v in vals if v is not None])


def _load_round_file(data_dir: Path, rnd: int) -> dict | None:
    path = data_dir / "rounds" / f"round_{_pad2(rnd)}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _feature_records(round_json: dict) -> list[dict]:
    """Every class's classification rows, flattened, for feature-drift PSI."""
    return [row for cls in round_json.get("classes", []) for row in cls.get("classification", [])]


def _drift_block(data_dir: Path, year: int, brier_by_round: list[tuple[int, float]]) -> dict | None:
    """Feature/output drift from the exported round files, if they exist."""
    completed = [rj for rnd in sorted({r for r, _ in brier_by_round})
                 if (rj := _load_round_file(data_dir, rnd)) is not None]
    if not completed:
        return None
    current = [rec for rj in completed[-_DRIFT_WINDOW:] for rec in _feature_records(rj)]
    baseline = [rec for rj in completed[-2 * _DRIFT_WINDOW:-_DRIFT_WINDOW]
                for rec in _feature_records(rj)]
    if not current or not baseline:
        return None
    report = drift.build_health_report(
        season=year,
        last_evaluated_round=completed[-1].get("round"),
        baseline_records=baseline,
        current_records=current,
        feature_columns=_FEATURE_COLUMNS,
        brier_by_round=brier_by_round,
    )
    return {
        "featureDrift": [
            {"feature": f.feature, "psi": f.psi, "severity": f.severity}
            for f in report.feature_drift
        ],
        "outputDrift": (
            {
                "rollingBrierRecent": report.output_drift.rolling_brier_recent,
                "rollingBrierBaseline": report.output_drift.rolling_brier_baseline,
                "relativeChange": report.output_drift.relative_change,
                "severity": report.output_drift.severity,
                "roundsCompared": report.output_drift.rounds_compared,
            }
            if report.output_drift else None
        ),
        "warnings": report.warnings,
        "alarms": report.alarms,
    }


def build_model_health(data_dir: Path, year: int, rounds: list[dict], season: dict) -> dict:
    brier_by_round = [
        (r["round"], b) for r in rounds if (b := _overall_round_win_brier(r)) is not None
    ]
    payload = {
        "season": year,
        "generatedAt": _utc_now_iso(),
        "lastEvaluatedRound": rounds[-1]["round"] if rounds else None,
        "brierByRound": [{"round": r, "brier": round(b, 6)} for r, b in brier_by_round],
        "forwardEval": {
            "roundsScored": season["roundsScored"],
            "classRoundsScored": season["classRoundsScored"],
            "meanPositionError": season["meanPositionError"],
            "winnerHitRate": season["winnerHitRate"],
            "podiumHitRate": season["podiumHitRate"],
            "overall": season["overall"],
            "byClass": season["byClass"],
            "modelVsBaselines": season["modelVsBaselines"],
            "walkForward": season["walkForward"],
        },
    }
    drift_block = _drift_block(data_dir, year, brier_by_round)
    if drift_block is not None:
        payload["featureDrift"] = drift_block["featureDrift"]
        payload["outputDrift"] = drift_block["outputDrift"]
        payload["warnings"] = drift_block["warnings"]
        payload["alarms"] = drift_block["alarms"]
    return payload


# --------------------------------------------------------------------------- #
def write(data_dir: Path, year: int) -> int:
    """Write ``forward_eval/*.json`` under ``data_dir`` + ``data_dir/model_health.json``.
    Returns the number of rounds scored."""
    source = WecDataSource()
    rounds = evaluate_season(source, year)
    fe_dir = data_dir / "forward_eval"
    fe_dir.mkdir(parents=True, exist_ok=True)
    for r in rounds:
        (fe_dir / f"round_{_pad2(r['round'])}.json").write_text(json.dumps(r, indent=2) + "\n")
    season = _season_summary(year, rounds)
    (fe_dir / "season.json").write_text(json.dumps(season, indent=2) + "\n")

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "model_health.json").write_text(
        json.dumps(build_model_health(data_dir, year, rounds, season), indent=2) + "\n"
    )
    return len(rounds)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--season", type=int, default=config.SEASON)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the website data root")
    p.add_argument("--allow-empty", action="store_true", help="exit 0 even if no rounds scorable")
    args = p.parse_args()
    n = write(args.out, args.season)
    if n == 0 and not args.allow_empty:
        print("forward_eval: no completed rounds to score", flush=True)
        return 1
    season = json.loads((args.out / "forward_eval" / "season.json").read_text())
    ov = season["overall"]
    v = season["modelVsBaselines"]
    print(
        f"forward_eval: scored {n} round(s) / {season['classRoundsScored']} class-rounds "
        f"→ {args.out}/forward_eval\n"
        f"  win-Brier    model={ov['model']['winBrier']} "
        f"lastRace={ov['lastRace']['winBrier']} seasonForm={ov['seasonForm']['winBrier']}\n"
        f"  podium-Brier model={ov['model']['podiumBrier']} "
        f"lastRace={ov['lastRace']['podiumBrier']} seasonForm={ov['seasonForm']['podiumBrier']}\n"
        f"  win+podium vs lastRace {v['vs']['lastRace']['delta']} "
        f"(notWorse={v['vs']['lastRace']['notWorse']}); "
        f"vs seasonForm {v['vs']['seasonForm']['delta']} "
        f"(notWorse={v['vs']['seasonForm']['notWorse']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
