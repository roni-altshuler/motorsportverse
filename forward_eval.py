"""Forward-time evaluation harness.

Scores predictions against actual finishing positions, race-by-race, with a
strict prior-data-only contract.  This is the evaluation metric a betting tool
actually cares about — per-driver position error, podium hit-rate, log-loss
against baselines, NDCG / Spearman ranking metrics — *not* in-sample lap-time
MAE.

Two operating modes:

1. **Score existing predictions** (default).  Reads predicted_results_<season>.json
   and season_results_<season>.json from the project root, computes per-round
   metrics, and writes a JSON report.  No model retraining; safe for CI.

2. **Backtest (planned)**.  Walk forward through completed rounds, retraining
   on rounds <R for each target R.  This requires a callable that fetches
   FastF1 data + builds features per round; the current per-race-script
   architecture does not expose that callable, so this mode is stubbed and
   will be implemented when models/lap_time.py is split out.

Per-round website output
------------------------
When ``--per-round-dir`` is given, each round's evaluation is also written as
``<dir>/round_NN.json`` so the website can render a per-round accuracy panel
without parsing the season-level report.  This is what
``.github/workflows/update_predictions.yml`` consumes — the post-race step
runs forward_eval and commits the per-round files alongside the existing
prediction JSON.

Baseline leaderboard
--------------------
A model that only beats "predict the same order as last race" isn't doing real
work.  Each round records a ``baselines`` block with the same metrics computed
against the **last-race-winner baseline** (use the *previous* round's actual
finishing order as this round's prediction).  Future baselines (pole-sitter,
championship-leader) will slot into the same dict — keep additive.

Usage::

    python forward_eval.py --season 2026
    python forward_eval.py --season 2026 --rounds 1-10
    python forward_eval.py --season 2026 --output reports/forward_eval_2026.json
    python forward_eval.py --season 2026 --per-round-dir website/public/data/forward_eval
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from leakage import LeakageError
from models.reliability import (
    MarketReliabilityReport,
    compute_market_report_from_probabilities,
    metrics_to_dict,
    save_reliability_diagram,
)

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
    spearman_correlation: float | None  # rank correlation, [-1, 1]; None if too few drivers
    ndcg_at_5: float | None             # ranking quality of predicted top-5 vs actual, [0, 1]
    biggest_misses: list[dict] = field(default_factory=list)
    # Baselines: same scoring against trivial / market predictors.  Keys are
    # baseline names; missing keys mean "not enough data to compute this round".
    # Schema per entry:
    #   {"mean_position_error": float, "winner_hit": bool, "podium_hits": int,
    #    "spearman_correlation": float | None}
    baselines: dict[str, dict] = field(default_factory=dict)


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
    prior_round_actual: dict[str, int] | None = None,
) -> RoundEvaluation:
    """Compute one round's evaluation metrics.

    Parameters
    ----------
    predicted, actual
        Driver-code → finishing-position maps.
    prior_round_actual
        Previous round's actual finishing order, used to score the
        "last race winner" baseline.  ``None`` skips the baseline.

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
            spearman_correlation=None,
            ndcg_at_5=None,
            baselines={},
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

    # Rank-quality metrics.  Skip when only 1-2 drivers overlap (correlation
    # is undefined / always 1).
    spearman = _spearman_correlation(
        [predicted[d] for d in common],
        [actual[d] for d in common],
    )
    ndcg = _ndcg_at_k(predicted=predicted, actual=actual, k=5)

    # Baselines: score the same metrics against a trivial predictor.
    baselines: dict[str, dict] = {}
    if prior_round_actual:
        baselines["last_race_winner"] = _baseline_score(prior_round_actual, actual)

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
        spearman_correlation=spearman,
        ndcg_at_5=ndcg,
        biggest_misses=biggest,
        baselines=baselines,
    )


def _spearman_correlation(predicted: list[int], actual: list[int]) -> float | None:
    """Spearman rank correlation between two integer rank vectors.

    Formula (no-ties): ρ = 1 - 6 Σ d² / (n(n²-1))  where d_i = pred_i - act_i.

    Ties are present whenever multiple drivers share a position (rare but
    possible in the predicted output — e.g. two drivers with identical lap
    times before tie-break).  We use the **average-rank** convention to
    handle ties, computing Pearson on the resulting rank columns.  For the
    common no-tie case this reduces to the standard formula.

    Returns ``None`` when n < 3 (correlation collapses to ±1 trivially).
    """
    n = len(predicted)
    if n < 3:
        return None
    pred_ranks = _average_ranks(predicted)
    act_ranks = _average_ranks(actual)
    mean_p = sum(pred_ranks) / n
    mean_a = sum(act_ranks) / n
    cov = sum((p - mean_p) * (a - mean_a) for p, a in zip(pred_ranks, act_ranks))
    var_p = sum((p - mean_p) ** 2 for p in pred_ranks)
    var_a = sum((a - mean_a) ** 2 for a in act_ranks)
    denom = math.sqrt(var_p * var_a)
    if denom <= 0:
        return None
    return cov / denom


def _average_ranks(values: list[int]) -> list[float]:
    """Convert raw positions to average ranks (ties get the mean rank)."""
    # sorted indices, lowest value first
    indexed = sorted(enumerate(values), key=lambda iv: iv[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        # Group ties
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # +1 for 1-indexed rank
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _ndcg_at_k(
    predicted: dict[str, int],
    actual: dict[str, int],
    k: int = 5,
) -> float | None:
    """Normalised Discounted Cumulative Gain over the predicted top-K.

    Each driver's relevance is ``n - actual_position`` (so P1 = highest gain,
    P-last = 0).  NDCG@K compares the gain accumulated by the *predicted*
    top-K to the ideal gain (sort by actual position).  Result ∈ [0, 1];
    1.0 = predicted top-K exactly matches the actual top-K.

    Returns ``None`` when fewer than K drivers are shared between maps.
    """
    common = sorted(set(predicted.keys()) & set(actual.keys()))
    if len(common) < k or k < 1:
        return None
    n = len(common)
    relevance = {d: float(n - actual[d]) for d in common}

    pred_topk = sorted(common, key=lambda d: predicted[d])[:k]
    ideal_topk = sorted(common, key=lambda d: actual[d])[:k]

    def dcg(order: list[str]) -> float:
        total = 0.0
        for rank, d in enumerate(order, start=1):
            total += relevance[d] / math.log2(rank + 1)
        return total

    actual_dcg = dcg(pred_topk)
    ideal_dcg = dcg(ideal_topk)
    if ideal_dcg <= 0:
        return None
    return actual_dcg / ideal_dcg


def _baseline_score(
    baseline_predicted: dict[str, int],
    actual: dict[str, int],
) -> dict[str, float | bool | int | None]:
    """Score a baseline predictor against actuals.  Lightweight subset of
    the full RoundEvaluation — just the metrics worth comparing."""
    common = sorted(set(baseline_predicted.keys()) & set(actual.keys()))
    if not common:
        return {
            "mean_position_error": None,
            "winner_hit": False,
            "podium_hits": 0,
            "spearman_correlation": None,
        }
    errors = [abs(baseline_predicted[d] - actual[d]) for d in common]
    pred_sorted = sorted(baseline_predicted.items(), key=lambda kv: kv[1])
    act_sorted = sorted(actual.items(), key=lambda kv: kv[1])
    pred_winner = pred_sorted[0][0] if pred_sorted else None
    act_winner = act_sorted[0][0] if act_sorted else None
    pred_top3 = {drv for drv, _ in pred_sorted[:3]}
    act_top3 = {drv for drv, _ in act_sorted[:3]}
    spearman = _spearman_correlation(
        [baseline_predicted[d] for d in common],
        [actual[d] for d in common],
    )
    return {
        "mean_position_error": round(sum(errors) / len(errors), 3),
        "winner_hit": bool(pred_winner is not None and pred_winner == act_winner),
        "podium_hits": len(pred_top3 & act_top3),
        "spearman_correlation": spearman,
    }


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
        # last-race-winner baseline: previous *completed* round's actuals.
        # Walk backward in case round R-1 was a DNQ / skipped slot.
        prior_actual: dict[str, int] | None = None
        for prior_rnd in range(rnd - 1, 0, -1):
            candidate = actual.get(prior_rnd)
            if candidate:
                prior_actual = candidate
                break
        evaluated.append(
            score_round(season, rnd, pred_round, act_round, prior_round_actual=prior_actual)
        )

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
            "mean_spearman": None,
            "mean_ndcg_at_5": None,
            "baselines": {},
        }
    n_rounds = len(rounds)
    total_drivers = sum(r.drivers_compared for r in rounds) or 1
    mean_err = sum(r.mean_position_error * r.drivers_compared for r in rounds) / total_drivers
    median_err = _median([r.median_position_error for r in rounds])
    winner_hits = sum(1 for r in rounds if r.winner_hit)
    podium_hits = sum(r.podium_hits for r in rounds) / (3 * n_rounds)
    exact_matches = sum(r.exact_matches for r in rounds) / total_drivers
    within_3 = sum(r.within_3 for r in rounds) / total_drivers

    spearmans = [r.spearman_correlation for r in rounds if r.spearman_correlation is not None]
    ndcgs = [r.ndcg_at_5 for r in rounds if r.ndcg_at_5 is not None]
    mean_spearman = round(sum(spearmans) / len(spearmans), 3) if spearmans else None
    mean_ndcg = round(sum(ndcgs) / len(ndcgs), 3) if ndcgs else None

    # Aggregate baseline metrics so the "is the model beating the trivial
    # predictor?" comparison is a single read.  Keys = baseline names that
    # appeared in *any* round; we average across the rounds where they did.
    baseline_summary: dict[str, dict] = {}
    baseline_names: set[str] = set()
    for r in rounds:
        baseline_names.update(r.baselines.keys())
    for name in sorted(baseline_names):
        present = [r.baselines.get(name) for r in rounds if name in r.baselines]
        present = [p for p in present if p is not None]
        if not present:
            continue
        errs = [p.get("mean_position_error") for p in present if isinstance(p.get("mean_position_error"), (int, float))]
        winners = sum(1 for p in present if p.get("winner_hit"))
        podiums = [int(p.get("podium_hits", 0)) for p in present]
        spear = [p.get("spearman_correlation") for p in present if isinstance(p.get("spearman_correlation"), (int, float))]
        baseline_summary[name] = {
            "rounds_compared": len(present),
            "mean_position_error": round(sum(errs) / len(errs), 3) if errs else None,
            "winner_hit_rate": round(winners / len(present), 3),
            "podium_hit_rate": round(sum(podiums) / (3 * len(present)), 3),
            "mean_spearman": round(sum(spear) / len(spear), 3) if spear else None,
        }

    return {
        "rounds_evaluated": n_rounds,
        "season_mean_error": round(mean_err, 3),
        "season_median_error": round(median_err, 3),
        "winner_hit_rate": round(winner_hits / n_rounds, 3),
        "podium_hit_rate": round(podium_hits, 3),
        "exact_match_rate": round(exact_matches, 3),
        "within_3_rate": round(within_3, 3),
        "mean_spearman": mean_spearman,
        "mean_ndcg_at_5": mean_ndcg,
        "baselines": baseline_summary,
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


def load_round_probabilities(
    probabilities_dir: Path,
    season: int,
    rounds: Iterable[int] | None = None,
) -> dict[int, dict]:
    """Read ``probabilities/round_NN.json`` files for ``rounds``.

    The probabilities directory is the same shape the website
    consumes (``website/public/data/probabilities/``). Each file
    carries ``classification[*].driver`` plus ``p_win``, ``p_podium``,
    ``p_top6``, ``p_top10`` per market — keys conform to the
    :mod:`models.calibration` payload schema.
    """
    if not probabilities_dir.exists():
        return {}
    out: dict[int, dict] = {}
    wanted = set(rounds) if rounds is not None else None
    for path in sorted(probabilities_dir.glob("round_*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        rnd = int(payload.get("round", 0))
        if rnd == 0:
            continue
        if wanted is not None and rnd not in wanted:
            continue
        out[rnd] = payload
    return out


def _actual_top_indicator(
    actual_round: dict[str, int],
    threshold: int,
) -> dict[str, int]:
    """Return ``{driver: 1}`` for finishing position <= threshold."""
    return {
        drv: int(pos <= threshold) for drv, pos in actual_round.items()
    }


def evaluate_calibration(
    season: int,
    probabilities_by_round: dict[int, dict],
    actual: dict[int, dict[str, int]],
) -> MarketReliabilityReport:
    """Aggregate per-round market probabilities + actuals → calibration metrics.

    Markets covered: ``win`` (pos==1), ``podium`` (pos<=3),
    ``top6`` (pos<=6), ``top10`` (pos<=10). Rounds that lack
    actuals are silently skipped. The output report can be
    serialised via :func:`MarketReliabilityReport.to_dict`.
    """
    pred: dict[str, list[float]] = {m: [] for m in ("win", "podium", "top6", "top10")}
    obs: dict[str, list[int]] = {m: [] for m in ("win", "podium", "top6", "top10")}
    market_threshold = {"win": 1, "podium": 3, "top6": 6, "top10": 10}

    for rnd, payload in probabilities_by_round.items():
        actual_round = actual.get(rnd, {})
        if not actual_round:
            continue
        # The probability JSON schema is ``markets: {<market>: [{driver, probability}, ...]}``.
        # We also accept the older ``classification[*].p_<market>`` flat shape
        # for backward compatibility.
        markets_block = payload.get("markets") or {}
        for market, threshold in market_threshold.items():
            entries = markets_block.get(market) or []
            for entry in entries:
                drv = entry.get("driver") or entry.get("code")
                p = entry.get("probability")
                if p is None:
                    p = entry.get("rawProbability")
                if drv is None or p is None or drv not in actual_round:
                    continue
                pred[market].append(float(p))
                obs[market].append(1 if actual_round[drv] <= threshold else 0)
        # Backward-compat path.
        for entry in payload.get("classification") or []:
            drv = entry.get("driver") or entry.get("code")
            if not drv or drv not in actual_round:
                continue
            for market, threshold in market_threshold.items():
                key = {
                    "win": "p_win",
                    "podium": "p_podium",
                    "top6": "p_top6",
                    "top10": "p_top10",
                }[market]
                p = entry.get(key)
                if p is None:
                    continue
                pred[market].append(float(p))
                obs[market].append(1 if actual_round[drv] <= threshold else 0)

    pred_nonempty = {m: v for m, v in pred.items() if v}
    obs_nonempty = {m: v for m, v in obs.items() if v}
    return compute_market_report_from_probabilities(pred_nonempty, obs_nonempty)


def write_reliability_plots(
    report: MarketReliabilityReport,
    output_dir: Path,
    *,
    title_prefix: str = "Reliability",
) -> list[Path]:
    """Render one PNG per market into ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for market, metrics in report.by_market.items():
        out = output_dir / f"reliability_{market}.png"
        save_reliability_diagram(
            metrics,
            out,
            title=f"{title_prefix} — {market}",
        )
        written.append(out)
    return written


def write_per_round_files(report: ForwardEvalReport, output_dir: Path) -> list[Path]:
    """Write one JSON file per evaluated round.

    Each file is named ``round_NN.json`` and contains a single
    ``RoundEvaluation`` plus a ``season`` field — schema the website
    accuracy page can consume one round at a time.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for r in report.rounds:
        target = output_dir / f"round_{r.round:02d}.json"
        payload = asdict(r)
        with target.open("w") as fh:
            json.dump(payload, fh, indent=2)
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--rounds", type=str, default=None,
                        help="Round filter (e.g. '1-10' or '3,5,7'). Default: all completed.")
    parser.add_argument("--predicted-file", type=Path, default=None)
    parser.add_argument("--actual-file", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Season-level JSON report path.")
    parser.add_argument("--per-round-dir", type=Path, default=None,
                        help="Optional directory for per-round JSON output "
                        "(consumed by website/public/data/forward_eval/round_NN.json).")
    parser.add_argument("--allow-empty", action="store_true",
                        help="When set, exit 0 (with a message) if no actuals "
                        "exist yet.  CI uses this on pre-race phases where the "
                        "forward-eval has nothing to score.")
    parser.add_argument("--probabilities-dir", type=Path, default=None,
                        help="Optional directory of probability JSON files "
                        "(website/public/data/probabilities/). When given, "
                        "calibration metrics (ECE/MCE/Brier per market) are "
                        "added to the season report.")
    parser.add_argument("--reliability-plots-dir", type=Path, default=None,
                        help="Optional directory where reliability diagrams "
                        "are saved (one PNG per market). Only used when "
                        "--probabilities-dir is also set.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    predicted_path = args.predicted_file or PROJECT_ROOT / f"predicted_results_{args.season}.json"
    actual_path = args.actual_file or PROJECT_ROOT / f"season_results_{args.season}.json"

    predicted = _load_results_json(predicted_path)
    actual = _load_results_json(actual_path)
    if not actual:
        msg = f"⚠️  No actual results found at {actual_path}; nothing to score."
        print(msg)
        return 0 if args.allow_empty else 1

    report = evaluate_season(
        season=args.season,
        predicted=predicted,
        actual=actual,
        rounds=_parse_rounds(args.rounds),
    )

    output_path = args.output if args.output.is_absolute() else (PROJECT_ROOT / args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(_report_to_jsonable(report), f, indent=2)

    per_round_written: list[Path] = []
    if args.per_round_dir is not None:
        per_round_dir = (
            args.per_round_dir
            if args.per_round_dir.is_absolute()
            else PROJECT_ROOT / args.per_round_dir
        )
        per_round_written = write_per_round_files(report, per_round_dir)

    calibration_summary: dict[str, object] | None = None
    plot_paths: list[Path] = []
    if args.probabilities_dir is not None:
        probabilities_dir = (
            args.probabilities_dir
            if args.probabilities_dir.is_absolute()
            else PROJECT_ROOT / args.probabilities_dir
        )
        probs = load_round_probabilities(
            probabilities_dir, args.season, rounds=_parse_rounds(args.rounds)
        )
        if probs:
            cal_report = evaluate_calibration(args.season, probs, actual)
            calibration_summary = cal_report.to_dict()
            # Splice into the on-disk season report so downstream consumers
            # don't have to re-parse the probabilities tree.
            existing = json.loads(output_path.read_text())
            existing["calibration"] = calibration_summary
            output_path.write_text(json.dumps(existing, indent=2))
            if args.reliability_plots_dir is not None:
                plots_dir = (
                    args.reliability_plots_dir
                    if args.reliability_plots_dir.is_absolute()
                    else PROJECT_ROOT / args.reliability_plots_dir
                )
                plot_paths = write_reliability_plots(
                    cal_report, plots_dir, title_prefix=f"{args.season} season"
                )

    if not args.quiet:
        print(f"📊 Forward-eval {args.season} — {report.summary['rounds_evaluated']} rounds")
        for r in report.rounds:
            wh = "✓" if r.winner_hit else "✗"
            spear = f"{r.spearman_correlation:.2f}" if r.spearman_correlation is not None else "—"
            ndcg = f"{r.ndcg_at_5:.2f}" if r.ndcg_at_5 is not None else "—"
            print(
                f"  R{r.round:02d}  meanErr={r.mean_position_error:5.2f}  "
                f"winner={wh}  podiumHits={r.podium_hits}/3  "
                f"ρ={spear}  NDCG@5={ndcg}"
            )
        try:
            display_path = output_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = output_path
        print(f"📝 Written {display_path}")
        if per_round_written:
            print(f"📝 Wrote {len(per_round_written)} per-round file(s) to "
                  f"{args.per_round_dir}")
        if calibration_summary is not None:
            markets = ", ".join(sorted(calibration_summary.keys()))
            print(f"📐 Calibration metrics computed for markets: {markets}")
            for market, m in calibration_summary.items():
                ece = m.get("ece")
                mce = m.get("mce")
                brier = m.get("brier")
                pieces = [
                    f"ECE={ece:.3f}" if isinstance(ece, (int, float)) else "ECE=—",
                    f"MCE={mce:.3f}" if isinstance(mce, (int, float)) else "MCE=—",
                    f"Brier={brier:.3f}" if isinstance(brier, (int, float)) else "Brier=—",
                ]
                print(f"    {market}: " + "  ".join(pieces))
        if plot_paths:
            print(f"📝 Wrote {len(plot_paths)} reliability plot(s) to "
                  f"{args.reliability_plots_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
