"""Historical backtest of the F2 prediction system against the real season.

This is the F2 analog of the F1 flagship's ``historical_backtest.py``. It
replays the model **leakage-safe** over every completed round — for round *N*
the forecast sees only rounds strictly before *N*, exactly the pre-race forecast
the website showed — and scores the predicted finishing order against the
official classification. Unlike ``forward_eval`` (which emits the per-round
website feed), this module produces the *dashboard* surface the Accuracy page's
Historical panel renders: a season roll-up, a per-driver "who is hard to
predict" table, and — the piece ``forward_eval`` doesn't have — **per-market
reliability diagrams** (predicted probability vs observed frequency) as PNGs.

What this measures
------------------
Two complementary things, both leak-safe:

1. **Positional accuracy** — predicted finishing order (feature race, the
   headline) vs the official classification: mean position error, within-N,
   winner/podium hits, Spearman, NDCG@5. Same shape as the F1 backtest so the
   frontend and the sibling F3 port read one contract.
2. **Probability calibration** — the model's win / podium / top-6 / top-10
   probabilities pooled across every scored race (both sprint and feature, for
   sample size) vs the realised binary outcomes, binned into a reliability
   curve with Brier + log-loss. A perfectly calibrated model sits on the y = x
   diagonal.

Honesty
-------
With one partial 2026 season there are only a handful of completed rounds, and
the backtest shows exactly that many — no synthetic rounds are fabricated to
pad the sample. Scoring is **finishers-only** (retirements are unranked in the
official classification), matching ``forward_eval`` and the F1 flagship.

Usage
-----

    python -m f2_predictions.historical_backtest [--season 2026] [--out <dir>]
        [--plots-dir <dir>]

Output
------
    website/public/data/historical_backtest/summary.json   dashboard payload
    website/public/data/reliability_plots/reliability_<market>.png   one per market
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # headless; no display needed
import matplotlib.pyplot as plt  # noqa: E402

from motorsport_core import eval as core_eval  # noqa: E402

from . import config, model, pipeline  # noqa: E402
from .datasource import F2DataSource  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DATA = PROJECT_ROOT / "website" / "public" / "data"
DEFAULT_OUT = WEB_DATA / "historical_backtest"
DEFAULT_PLOTS = WEB_DATA / "reliability_plots"

RACE_TYPES = (model.SPRINT, model.FEATURE)
MARKETS = ("win", "podium", "top6", "top10")
# Set-membership thresholds per market (a finisher "hits" the market at pos <= k).
MARKET_THRESHOLD = {"win": 1, "podium": 3, "top6": 6, "top10": 10}

# F2 electric-blue accent (tokens.css --accent-f1-red) so the PNGs match the site.
_ACCENT = "#1E9BD7"
_SURFACE = "#141414"
_INK = "#e8e8e8"
_MUTED = "#8a8a8a"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Leakage-safe replay
# --------------------------------------------------------------------------- #
def _round_actuals(source: F2DataSource, year: int, rnd: int) -> dict[str, dict[str, int]]:
    """Classified finishers per race type: {race_type: {code: position}}."""
    races = source.race_results_for_round(year, rnd)
    return {
        rt: {r.competitor: r.position for r in races[rt] if r.position is not None}
        for rt in RACE_TYPES
    }


def _predicted_positions(order: Sequence[str]) -> dict[str, int]:
    """Finishing order (codes, fastest first) → {code: 1-based position}."""
    return {code: i for i, code in enumerate(order, start=1)}


def _market_pairs(probs: dict[str, float], actual: dict[str, int], threshold: int) -> list[tuple[float, int]]:
    """(predicted_prob, realised_outcome) pairs over the classified finishers."""
    if not actual:
        return []
    if threshold == 1:  # win: exactly one positive per race (the actual winner)
        winner = min(actual, key=actual.get)
        return [(float(probs.get(c, 0.0)), 1 if c == winner else 0) for c in actual]
    return [(float(probs.get(c, 0.0)), 1 if pos <= threshold else 0) for c, pos in actual.items()]


def _round_block(rnd: int, venue_name: str, predicted: dict[str, int], actual: dict[str, int]) -> dict:
    """F1-parity per-round metric block for the feature race."""
    common = sorted(set(predicted) & set(actual))
    score = core_eval.score_round(predicted, actual)
    errors = [abs(predicted[c] - actual[c]) for c in common]
    biggest = sorted(
        (
            {
                "driver": c,
                "predicted": predicted[c],
                "actual": actual[c],
                "delta": predicted[c] - actual[c],
                "absDelta": abs(predicted[c] - actual[c]),
            }
            for c in common
        ),
        key=lambda r: r["absDelta"],
        reverse=True,
    )[:5]
    return {
        "round": rnd,
        "venueName": venue_name,
        "drivers_compared": score.get("n", len(common)),
        "mean_position_error": score.get("mean_position_error"),
        "median_position_error": float(median(errors)) if errors else None,
        "rmse_position_error": (
            round(math.sqrt(mean(e * e for e in errors)), 3) if errors else None
        ),
        "exact_matches": score.get("exact_matches", 0),
        "within_3": score.get("within_3", 0),
        "within_5": score.get("within_5", 0),
        "winner_hit": bool(score.get("winner_hit", False)),
        "podium_hits": score.get("podium_hits", 0),
        "spearman_correlation": score.get("spearman_correlation"),
        "ndcg_at_5": score.get("ndcg_at_5"),
        "biggest_misses": biggest,
    }


def replay(source: F2DataSource, year: int) -> dict:
    """Walk every completed round forward, scoring positions + market probs.

    Returns a dict with the per-round feature-race blocks, per-driver error
    aggregation (feature race), and pooled per-market (prob, outcome) pairs.
    """
    rounds: list[dict] = []
    driver_errors: dict[str, list[int]] = defaultdict(list)
    market_pairs: dict[str, list[tuple[float, int]]] = {m: [] for m in MARKETS}
    feature_rows = 0

    for rnd in range(1, config.COMPLETED_ROUNDS + 1):
        actual = _round_actuals(source, year, rnd)
        if not actual[model.FEATURE]:
            continue
        fc = pipeline.forecast_round(source, year, rnd)

        # Positional accuracy — feature race (the headline).
        predicted = _predicted_positions(fc.feature.order)
        rounds.append(_round_block(rnd, fc.venue_name, predicted, actual[model.FEATURE]))
        for c in set(predicted) & set(actual[model.FEATURE]):
            driver_errors[c].append(abs(predicted[c] - actual[model.FEATURE][c]))
            feature_rows += 1

        # Probability calibration — pool both races for sample size.
        for rt in RACE_TYPES:
            race = getattr(fc, rt)
            probs_by_market = {
                "win": race.markets.p_win,
                "podium": race.markets.p_podium,
                "top6": race.markets.p_top6,
                "top10": race.markets.p_top10,
            }
            for m in MARKETS:
                market_pairs[m].extend(
                    _market_pairs(probs_by_market[m], actual[rt], MARKET_THRESHOLD[m])
                )

    return {
        "rounds": rounds,
        "driver_errors": dict(driver_errors),
        "market_pairs": market_pairs,
        "feature_rows": feature_rows,
    }


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _season_summary(rounds: list[dict]) -> dict:
    if not rounds:
        return {
            "rounds_evaluated": 0,
            "season_mean_error": None,
            "season_median_error": None,
            "winner_hit_rate": None,
            "podium_hit_rate": None,
            "exact_match_rate": None,
            "within_3_rate": None,
            "within_5_rate": None,
            "mean_spearman": None,
            "mean_ndcg_at_5": None,
        }
    n_drivers = [r["drivers_compared"] for r in rounds]
    total_drivers = sum(n_drivers) or 1
    maes = [r["mean_position_error"] for r in rounds if r["mean_position_error"] is not None]
    medians = [r["median_position_error"] for r in rounds if r["median_position_error"] is not None]
    spearmans = [r["spearman_correlation"] for r in rounds if r["spearman_correlation"] is not None]
    ndcgs = [r["ndcg_at_5"] for r in rounds if r["ndcg_at_5"] is not None]
    return {
        "rounds_evaluated": len(rounds),
        "season_mean_error": round(mean(maes), 3) if maes else None,
        "season_median_error": round(float(median(medians)), 3) if medians else None,
        "winner_hit_rate": round(sum(1 for r in rounds if r["winner_hit"]) / len(rounds), 3),
        "podium_hit_rate": round(sum(r["podium_hits"] for r in rounds) / (3 * len(rounds)), 3),
        "exact_match_rate": round(sum(r["exact_matches"] for r in rounds) / total_drivers, 3),
        "within_3_rate": round(sum(r["within_3"] for r in rounds) / total_drivers, 3),
        "within_5_rate": round(sum(r["within_5"] for r in rounds) / total_drivers, 3),
        "mean_spearman": round(mean(spearmans), 3) if spearmans else None,
        "mean_ndcg_at_5": round(mean(ndcgs), 3) if ndcgs else None,
    }


def _per_driver(driver_errors: dict[str, list[int]]) -> list[dict]:
    out = []
    for drv, errors in driver_errors.items():
        if not errors:
            continue
        out.append(
            {
                "driver": drv,
                "rounds": len(errors),
                "mae": round(mean(errors), 3),
                "within_3_rate": round(sum(1 for e in errors if e <= 3) / len(errors), 3),
            }
        )
    out.sort(key=lambda r: r["mae"])
    return out


def _reliability_bins(pairs: list[tuple[float, int]], n_bins: int = 10) -> list[dict]:
    """Bin (prob, outcome) pairs into a reliability curve on [0, 1]."""
    if not pairs:
        return []
    bins: list[dict] = []
    for i in range(n_bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        # Last bin is closed on the right so a p=1.0 lands somewhere.
        in_bin = [
            (p, y) for (p, y) in pairs if (lo <= p < hi or (i == n_bins - 1 and p == 1.0))
        ]
        if not in_bin:
            continue
        preds = [p for p, _ in in_bin]
        outs = [y for _, y in in_bin]
        bins.append(
            {
                "binLo": round(lo, 3),
                "binHi": round(hi, 3),
                "meanPred": round(mean(preds), 4),
                "empirical": round(mean(outs), 4),
                "count": len(in_bin),
            }
        )
    return bins


def _market_report(pairs: list[tuple[float, int]]) -> dict:
    """Brier + log-loss + reliability bins for one market."""
    if not pairs:
        return {"brier": None, "logLoss": None, "samples": 0, "reliability": []}
    eps = 1e-12
    brier = mean((p - y) ** 2 for p, y in pairs)
    ll = mean(
        -(y * math.log(min(1 - eps, max(eps, p))) + (1 - y) * math.log(min(1 - eps, max(eps, 1 - p))))
        for p, y in pairs
    )
    return {
        "brier": round(brier, 6),
        "logLoss": round(ll, 6),
        "samples": len(pairs),
        "reliability": _reliability_bins(pairs),
    }


# --------------------------------------------------------------------------- #
# Reliability PNGs
# --------------------------------------------------------------------------- #
def _save_reliability_png(market: str, report: dict, path: Path) -> None:
    bins = report.get("reliability") or []
    fig, ax = plt.subplots(figsize=(4.4, 4.4), dpi=140)
    fig.patch.set_facecolor(_SURFACE)
    ax.set_facecolor(_SURFACE)

    # Perfect-calibration diagonal.
    ax.plot([0, 1], [0, 1], color=_MUTED, linestyle=(0, (5, 4)), linewidth=1.2, zorder=1)

    if bins:
        xs = [b["meanPred"] for b in bins]
        ys = [b["empirical"] for b in bins]
        counts = [b["count"] for b in bins]
        cmax = max(counts) or 1
        sizes = [40 + 320 * (c / cmax) for c in counts]
        ax.scatter(xs, ys, s=sizes, color=_ACCENT, edgecolors="#0a0a0a",
                   linewidths=0.8, alpha=0.9, zorder=3)
    else:
        ax.text(0.5, 0.5, "no samples", color=_MUTED, ha="center", va="center",
                transform=ax.transAxes, fontsize=10)

    title = {"win": "Win", "podium": "Podium", "top6": "Top 6", "top10": "Top 10"}.get(market, market)
    brier = report.get("brier")
    subtitle = f"Brier {brier:.4f}" if brier is not None else ""
    ax.set_title(f"{title} calibration", color=_INK, fontsize=12, pad=10)
    if subtitle:
        ax.text(0.02, 0.96, subtitle, color=_MUTED, fontsize=9,
                transform=ax.transAxes, va="top")
    ax.set_xlabel("Predicted probability", color=_MUTED, fontsize=9)
    ax.set_ylabel("Observed frequency", color=_MUTED, fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    for spine in ax.spines.values():
        spine.set_color("#2a2a2a")
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.grid(True, color="#242424", linewidth=0.6)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=_SURFACE, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def backtest(year: int) -> dict:
    """Run the full backtest and return the dashboard payload."""
    source = F2DataSource()
    rep = replay(source, year)
    rounds = rep["rounds"]
    summary = _season_summary(rounds)
    per_driver = _per_driver(rep["driver_errors"])
    markets = {m: _market_report(rep["market_pairs"][m]) for m in MARKETS}
    # The plot path is relative to public/data so the site can resolve it.
    for m in MARKETS:
        markets[m]["plot"] = f"reliability_plots/reliability_{m}.png"

    payload = {
        "season": year,
        "seasons": [year],
        "generatedAt": _utc_now_iso(),
        "source": f"leakage-safe replay of the F2 model over data/official_{year}.json",
        "scoring": "pre-race forecast vs official classification, finishers-only",
        "finishersOnly": True,
        "roundsEvaluated": summary["rounds_evaluated"],
        "totalRows": rep["feature_rows"],
        "perSeason": [{"season": year, "summary": summary, "rounds": rounds}],
        "perDriver": per_driver,
        "markets": markets,
    }
    return payload


def write_outputs(payload: dict, out_dir: Path, plots_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    written = [out_dir / "summary.json"]
    for m in MARKETS:
        png = plots_dir / f"reliability_{m}.png"
        _save_reliability_png(m, payload["markets"][m], png)
        written.append(png)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", type=int, default=config.SEASON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--plots-dir", type=Path, default=DEFAULT_PLOTS)
    args = parser.parse_args(argv)

    payload = backtest(args.season)
    market_reports = payload["markets"]
    written = write_outputs(payload, args.out, args.plots_dir)

    s = payload["perSeason"][0]["summary"]
    n = s["rounds_evaluated"]
    print(f"📊 F2 historical backtest — season {args.season}: {n} round(s) scored")
    if n:
        print(
            f"  MAE={s['season_mean_error']}  within-3={s['within_3_rate']:.1%}  "
            f"podium-hits={s['podium_hit_rate']:.1%}  winner-hits={s['winner_hit_rate']:.1%}  "
            f"NDCG@5={s['mean_ndcg_at_5']}"
        )
        for m in MARKETS:
            rep = market_reports[m]
            print(f"  {m:>6}: Brier={rep['brier']}  logLoss={rep['logLoss']}  n={rep['samples']}")
    print(f"📝 Wrote {len(written)} file(s): {args.out}/summary.json + {len(MARKETS)} reliability PNG(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
