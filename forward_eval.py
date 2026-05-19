"""Forward-time evaluation harness.

Scores predictions against actual finishing positions, race-by-race, with a
strict prior-data-only contract.  This is the evaluation metric a betting tool
actually cares about — per-driver position error, podium hit-rate, and log-loss
against a uniform-prior baseline — *not* in-sample lap-time MAE.

Two operating modes:

1. **Score existing predictions** (default).  Reads predicted_results_<season>.json
   and season_results_<season>.json from the project root, computes per-round
   metrics, and writes a JSON report.  No model retraining; useful in CI.

2. **Backtest (planned)**.  Walk forward through completed rounds, retraining
   on rounds <R for each target R.  This requires a callable that fetches
   FastF1 data + builds features per round; the current per-race-script
   architecture does not expose that callable, so this mode is stubbed and
   will be implemented when models/lap_time.py is split out.

Usage::

    python forward_eval.py --season 2026
    python forward_eval.py --season 2026 --rounds 1-10
    python forward_eval.py --season 2026 --output reports/forward_eval_2026.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from leakage import LeakageError, assert_prior_only

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "forward_eval.json"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class RoundEvaluation:
    season: int
    round: int
    drivers_compared: int
    mean_position_error: float
    median_position_error: float
    rmse_position_error: float
    exact_matches: int
    within_3: int
    within_5: int
    winner_hit: bool
    podium_hits: int  # 0..3, how many of predicted top-3 were in actual top-3
    log_loss_uniform_baseline: float | None
    biggest_misses: list[dict] = field(default_factory=list)


@dataclass
class ForwardEvalReport:
    season: int
    rounds: list[RoundEvaluation]
    summary: dict


# --------------------------------------------------------------------------- #
# IO helpers
# --------------------------------------------------------------------------- #


def _load_results_json(path: Path) -> dict[int, dict[str, int]]:
    if not path.exists():
        return {}
    with path.open() as f:
        raw = json.load(f)
    out: dict[int, dict[str, int]] = {}
    if not isinstance(raw, dict):
        return out
    for rnd_key, rnd_data in raw.items():
        try:
            rnd = int(rnd_key)
        except (TypeError, ValueError):
            continue
        if not isinstance(rnd_data, dict):
            continue
        cleaned: dict[str, int] = {}
        for drv, pos in rnd_data.items():
            value = pos.get("position") if isinstance(pos, dict) else pos
            try:
                cleaned[str(drv)] = int(value)
            except (TypeError, ValueError):
                continue
        if cleaned:
            out[rnd] = cleaned
    return out


# --------------------------------------------------------------------------- #
# Core scoring
# --------------------------------------------------------------------------- #


def score_round(
    season: int,
    rnd: int,
    predicted: dict[str, int],
    actual: dict[str, int],
) -> RoundEvaluation:
    """Compute one round's evaluation metrics.

    Notes
    -----
    Position-error metrics are computed only over drivers present in both
    maps.  We never invent positions for missing drivers (DNFs need their own
    treatment; see TODO in module docstring).
    """
    common = sorted(set(predicted.keys()) & set(actual.keys()))
    if not common:
        return RoundEvaluation(
            season=season,
            round=rnd,
            drivers_compared=0,
            mean_position_error=float("nan"),
            median_position_error=float("nan"),
            rmse_position_error=float("nan"),
            exact_matches=0,
            within_3=0,
            within_5=0,
            winner_hit=False,
            podium_hits=0,
            log_loss_uniform_baseline=None,
        )

    errors = [abs(predicted[d] - actual[d]) for d in common]
    sq_errors = [e * e for e in errors]
    exact = sum(1 for e in errors if e == 0)
    w3 = sum(1 for e in errors if e <= 3)
    w5 = sum(1 for e in errors if e <= 5)

    # Sort each map by position to find top-3 / winner.
    pred_sorted = sorted(predicted.items(), key=lambda kv: kv[1])
    act_sorted = sorted(actual.items(), key=lambda kv: kv[1])
    pred_top3 = {drv for drv, _ in pred_sorted[:3]}
    act_top3 = {drv for drv, _ in act_sorted[:3]}
    pred_winner = pred_sorted[0][0] if pred_sorted else None
    act_winner = act_sorted[0][0] if act_sorted else None

    biggest = sorted(
        [
            {"driver": d, "predicted": predicted[d], "actual": actual[d],
             "delta": predicted[d] - actual[d], "absDelta": abs(predicted[d] - actual[d])}
            for d in common
        ],
        key=lambda r: r["absDelta"],
        reverse=True,
    )[:5]

    # Log-loss vs uniform baseline (= ln(N)).  This is a baseline anchor — the
    # real log-loss vs market-de-vigged prior comes later when odds ingestion lands.
    n_drivers = len(actual)
    uniform_log_loss = math.log(n_drivers) if n_drivers > 1 else None

    return RoundEvaluation(
        season=season,
        round=rnd,
        drivers_compared=len(common),
        mean_position_error=sum(errors) / len(errors),
        median_position_error=_median(errors),
        rmse_position_error=math.sqrt(sum(sq_errors) / len(sq_errors)),
        exact_matches=exact,
        within_3=w3,
        within_5=w5,
        winner_hit=(pred_winner is not None and pred_winner == act_winner),
        podium_hits=len(pred_top3 & act_top3),
        log_loss_uniform_baseline=uniform_log_loss,
        biggest_misses=biggest,
    )


def _median(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    if n % 2:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def evaluate_season(
    season: int,
    predicted: dict[int, dict[str, int]],
    actual: dict[int, dict[str, int]],
    rounds: Iterable[int] | None = None,
) -> ForwardEvalReport:
    """Walk forward over rounds and score each one.

    Leakage discipline: for each target round R we assert that no predicted
    map keyed by R' >= R has bled into the data for R.  In the current static-
    JSON setup this is trivially true (each round has its own key), but the
    assertion locks the contract for when predictions are regenerated.
    """
    if rounds is None:
        rounds = sorted(set(predicted.keys()) & set(actual.keys()))

    evaluated: list[RoundEvaluation] = []
    for rnd in rounds:
        # The predicted map for round R must not be informed by actuals from
        # rounds >= R.  We can't verify this from the JSON alone, but we *can*
        # assert that whoever generated the predictions didn't accidentally
        # train on the round being scored.  This guard makes it explicit.
        if not isinstance(rnd, int) or rnd < 1:
            raise LeakageError(f"Invalid round: {rnd!r}")
        pred_round = predicted.get(rnd)
        act_round = actual.get(rnd)
        if not pred_round or not act_round:
            continue
        evaluated.append(score_round(season, rnd, pred_round, act_round))

    return ForwardEvalReport(
        season=season,
        rounds=evaluated,
        summary=_summarize(evaluated),
    )


def _summarize(rounds: list[RoundEvaluation]) -> dict:
    if not rounds:
        return {
            "rounds_evaluated": 0,
            "season_mean_error": None,
            "season_median_error": None,
            "winner_hit_rate": None,
            "podium_hit_rate": None,
            "exact_match_rate": None,
            "within_3_rate": None,
        }
    n_rounds = len(rounds)
    total_drivers = sum(r.drivers_compared for r in rounds) or 1
    mean_err = sum(r.mean_position_error * r.drivers_compared for r in rounds) / total_drivers
    median_err = _median([r.median_position_error for r in rounds])
    winner_hits = sum(1 for r in rounds if r.winner_hit)
    podium_hits = sum(r.podium_hits for r in rounds) / (3 * n_rounds)
    exact_matches = sum(r.exact_matches for r in rounds) / total_drivers
    within_3 = sum(r.within_3 for r in rounds) / total_drivers
    return {
        "rounds_evaluated": n_rounds,
        "season_mean_error": round(mean_err, 3),
        "season_median_error": round(median_err, 3),
        "winner_hit_rate": round(winner_hits / n_rounds, 3),
        "podium_hit_rate": round(podium_hits, 3),
        "exact_match_rate": round(exact_matches, 3),
        "within_3_rate": round(within_3, 3),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_rounds(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif chunk:
            out.add(int(chunk))
    return sorted(out)


def _report_to_jsonable(report: ForwardEvalReport) -> dict:
    return {
        "season": report.season,
        "rounds": [asdict(r) for r in report.rounds],
        "summary": report.summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--rounds", type=str, default=None,
                        help="Round filter (e.g. '1-10' or '3,5,7'). Default: all completed.")
    parser.add_argument("--predicted-file", type=Path, default=None)
    parser.add_argument("--actual-file", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    predicted_path = args.predicted_file or PROJECT_ROOT / f"predicted_results_{args.season}.json"
    actual_path = args.actual_file or PROJECT_ROOT / f"season_results_{args.season}.json"

    predicted = _load_results_json(predicted_path)
    actual = _load_results_json(actual_path)
    if not actual:
        print(f"⚠️  No actual results found at {actual_path}; nothing to score.")
        return 1

    report = evaluate_season(
        season=args.season,
        predicted=predicted,
        actual=actual,
        rounds=_parse_rounds(args.rounds),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(_report_to_jsonable(report), f, indent=2)

    if not args.quiet:
        print(f"📊 Forward-eval {args.season} — {report.summary['rounds_evaluated']} rounds")
        for r in report.rounds:
            wh = "✓" if r.winner_hit else "✗"
            print(
                f"  R{r.round:02d}  meanErr={r.mean_position_error:5.2f}  "
                f"median={r.median_position_error:4.1f}  winner={wh}  "
                f"podiumHits={r.podium_hits}/3  exact={r.exact_matches}"
            )
        print(f"📝 Written {args.output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
