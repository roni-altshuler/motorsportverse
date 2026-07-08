"""CLI: load production + candidate forward-eval streams and decide.

Reads forward-eval JSONs from two directories (one per variant), applies
the rule in ``models/promotion.py``, and writes
``website/public/data/promotion_status.json``.  The website's accuracy
page can render the recommendation alongside the registered ensemble's
training provenance.

Directory layout (caller's responsibility to create):

    website/public/data/forward_eval/                # production (legacy)
    website/public/data/forward_eval_candidate/      # candidate variant

The default-production-variant convention preserves backwards compat:
the existing forward_eval per-round files (written by forward_eval.py)
are treated as the production stream automatically.

Usage::

    python promotion_decision.py --season 2026
    python promotion_decision.py --season 2026 --candidate-dir path/to/candidate
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from models.promotion import (
    DEFAULT_MAX_PER_ROUND_REGRESSION,
    DEFAULT_MIN_ROUNDS_TO_DECIDE,
    DEFAULT_RELATIVE_IMPROVEMENT_THRESHOLD,
    DEFAULT_TRAILING_WINDOW,
    PromotionDecision,
    evaluate_promotion,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_FORWARD_EVAL = PROJECT_ROOT / "website" / "public" / "data" / "forward_eval"
WEBSITE_FORWARD_EVAL_CANDIDATE = (
    PROJECT_ROOT / "website" / "public" / "data" / "forward_eval_candidate"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "website" / "public" / "data" / "promotion_status.json"

# Metric key inside the per-round forward_eval JSON we treat as the
# "lower-is-better" comparison score.  Matches drift_report.py's choice.
SCORE_KEY: str = "rmse_position_error"


def _load_per_round_scores(directory: Path) -> list[tuple[int, float]]:
    """Read forward_eval/round_NN.json files, extract the comparison score."""
    out: list[tuple[int, float]] = []
    if not directory.exists():
        return out
    for path in sorted(directory.glob("round_*.json")):
        try:
            rnd = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        score = payload.get(SCORE_KEY)
        if score is None:
            continue
        try:
            out.append((rnd, float(score)))
        except (TypeError, ValueError):
            continue
    return out


def decision_to_jsonable(
    decision: PromotionDecision, *, season: int, candidate_dir: Path
) -> dict:
    payload = asdict(decision)
    payload.update(
        {
            "season": season,
            "candidateSource": str(candidate_dir),
            "scoreKey": SCORE_KEY,
        }
    )
    return payload


# Headline metric keys inside the per-round forward_eval JSONs. winner_hit is
# a bool; podium_hits is 0..3; top10_overlap is 0..10 (added 2026-07).
_HEADLINE_KEYS = ("winner_hit", "podium_hits", "top10_overlap", "mean_position_error")


def _load_per_round_headline(directory: Path) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not directory.exists():
        return out
    for path in sorted(directory.glob("round_*.json")):
        try:
            rnd = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        out[rnd] = {k: payload.get(k) for k in _HEADLINE_KEYS}
    return out


def _summarize_headline(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"rounds": 0}
    winner_hits = sum(1 for r in rows if r.get("winner_hit"))
    podium = [r.get("podium_hits") for r in rows if r.get("podium_hits") is not None]
    top10 = [r.get("top10_overlap") for r in rows if r.get("top10_overlap") is not None]
    mae = [r.get("mean_position_error") for r in rows if r.get("mean_position_error") is not None]
    podium_pct = round(sum(podium) / (3 * len(podium)) * 100, 1) if podium else None
    points_pct = round(sum(top10) / (10 * len(top10)) * 100, 1) if top10 else None
    blend = (
        round(0.6 * podium_pct + 0.4 * points_pct, 1)
        if podium_pct is not None and points_pct is not None
        else None
    )
    return {
        "rounds": n,
        "winnerHits": winner_hits,
        "winnerHitPct": round(winner_hits / n * 100, 1),
        "podiumSetPct": podium_pct,
        "pointsSetPct": points_pct,
        "blendPct": blend,
        "meanError": round(sum(mae) / len(mae), 2) if mae else None,
    }


def build_headline_comparison(production_dir: Path, candidate_dir: Path) -> dict | None:
    """Walk-forward headline metrics (winner-hit + podium/points blend) for the
    production and candidate streams over their COMMON rounds, plus a verdict.

    The site's headline metrics are winner-hit and the 0.6*podium + 0.4*points
    blend — the guarded RMSE rule alone can hold a candidate that dramatically
    improves winner calls, so this block surfaces the comparison that actually
    decides shipping (candidate must beat production on BOTH headline metrics).
    Additive to promotion_status.json.
    """
    prod = _load_per_round_headline(production_dir)
    cand = _load_per_round_headline(candidate_dir)
    common = sorted(set(prod) & set(cand))
    if not common:
        return None
    prod_summary = _summarize_headline([prod[r] for r in common])
    cand_summary = _summarize_headline([cand[r] for r in common])
    wins_winner = (
        prod_summary.get("winnerHitPct") is not None
        and cand_summary.get("winnerHitPct") is not None
        and cand_summary["winnerHitPct"] > prod_summary["winnerHitPct"]
    )
    ties_winner = cand_summary.get("winnerHitPct") == prod_summary.get("winnerHitPct")
    wins_blend = (
        prod_summary.get("blendPct") is not None
        and cand_summary.get("blendPct") is not None
        and cand_summary["blendPct"] > prod_summary["blendPct"]
    )
    ties_blend = cand_summary.get("blendPct") == prod_summary.get("blendPct")
    if (wins_winner and (wins_blend or ties_blend)) or (ties_winner and wins_blend):
        verdict = "candidate-better"
    elif ties_winner and ties_blend:
        verdict = "parity"
    elif wins_winner or wins_blend:
        verdict = "mixed"
    else:
        verdict = "production-better"
    return {
        "roundsCompared": len(common),
        "commonRounds": common,
        "production": prod_summary,
        "candidate": cand_summary,
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply the promotion rule to production vs candidate "
        "forward-eval streams and write the decision JSON."
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--production-dir",
        type=Path,
        default=WEBSITE_FORWARD_EVAL,
        help="Directory of per-round forward-eval JSONs for the production "
        "model.  Default: website/public/data/forward_eval",
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=WEBSITE_FORWARD_EVAL_CANDIDATE,
        help="Directory of per-round forward-eval JSONs for the candidate "
        "model.  Default: website/public/data/forward_eval_candidate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write promotion_status.json.",
    )
    parser.add_argument(
        "--min-rounds",
        type=int,
        default=DEFAULT_MIN_ROUNDS_TO_DECIDE,
        help=f"Minimum common rounds before any non-hold decision (default {DEFAULT_MIN_ROUNDS_TO_DECIDE}).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_RELATIVE_IMPROVEMENT_THRESHOLD,
        help=f"Relative improvement threshold for promotion (default {DEFAULT_RELATIVE_IMPROVEMENT_THRESHOLD * 100:.0f}%%).",
    )
    parser.add_argument(
        "--max-per-round-regression",
        type=float,
        default=DEFAULT_MAX_PER_ROUND_REGRESSION,
        help=f"Max single-round regression that still permits promotion (default {DEFAULT_MAX_PER_ROUND_REGRESSION * 100:.0f}%%).",
    )
    parser.add_argument(
        "--trailing-window",
        type=int,
        default=DEFAULT_TRAILING_WINDOW,
        help=f"How many recent overlapping rounds to compare on (default {DEFAULT_TRAILING_WINDOW}).",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit 0 when no candidate scores exist (pre-A/B-launch).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="When the decision is 'promote', append an entry to "
        "auto_promotion_log.json so CI / operators can audit the chain "
        "of recommendations.  No artefact swap is performed by this "
        "flag — the registry copy is left to a separate workflow step.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    production_scores = _load_per_round_scores(args.production_dir)
    candidate_scores = _load_per_round_scores(args.candidate_dir)
    if not candidate_scores:
        msg = (
            f"⚠️  No candidate scores in {args.candidate_dir}; "
            f"nothing to compare against."
        )
        print(msg)
        return 0 if args.allow_empty else 1

    decision = evaluate_promotion(
        production_scores=production_scores,
        candidate_scores=candidate_scores,
        min_rounds_to_decide=args.min_rounds,
        relative_improvement_threshold=args.threshold,
        max_per_round_regression=args.max_per_round_regression,
        trailing_window=args.trailing_window,
    )

    payload = decision_to_jsonable(
        decision, season=args.season, candidate_dir=args.candidate_dir
    )
    # Headline walk-forward comparison (winner-hit + podium/points blend) —
    # the metric family that actually decides shipping. Additive field.
    headline = build_headline_comparison(args.production_dir, args.candidate_dir)
    if headline is not None:
        payload["headline"] = headline

    output_path = (
        args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        json.dump(payload, fh, indent=2)

    if args.apply and decision.decision == "promote":
        from datetime import datetime, timezone

        log_path = output_path.parent / "auto_promotion_log.json"
        existing: list[dict] = []
        if log_path.exists():
            try:
                with log_path.open("r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                    if isinstance(loaded, list):
                        existing = loaded
            except (OSError, json.JSONDecodeError):
                existing = []
        existing.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "season": args.season,
                "decision": decision.decision,
                "reason": decision.reason,
                "rounds_compared": decision.rounds_compared,
                "mean_production": decision.mean_production,
                "mean_candidate": decision.mean_candidate,
                "relative_change": decision.relative_change,
            }
        )
        with log_path.open("w") as fh:
            json.dump(existing, fh, indent=2)
        if not args.quiet:
            print(f"📜 Appended promote entry to {log_path.name}")

    if not args.quiet:
        emoji = {"promote": "✅", "hold": "⏸️", "demote": "⛔"}.get(decision.decision, "?")
        print(f"{emoji} Promotion decision: {decision.decision.upper()}")
        print(f"   reason: {decision.reason}")
        print(f"   rounds compared: {decision.rounds_compared}")
        if decision.mean_production is not None:
            print(
                f"   mean production={decision.mean_production:.4f}  "
                f"mean candidate={decision.mean_candidate:.4f}  "
                f"Δ={decision.relative_change:+.1%}"
            )
        try:
            display_path = output_path.relative_to(PROJECT_ROOT)
        except ValueError:
            display_path = output_path
        print(f"📝 Written {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
