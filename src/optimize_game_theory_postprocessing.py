#!/usr/bin/env python3
"""Tune game-theory postprocessing scale against completed-round accuracy."""

import argparse
import json
import os
from datetime import datetime

from benchmark_game_theory_upgrades import _diff, _run_variant


def _parse_scale_list(raw):
    values = []
    for chunk in str(raw).split(","):
        token = chunk.strip()
        if not token:
            continue
        values.append(float(token))
    return sorted(set(values))


def _objective(delta):
    """Higher is better; rewards lower errors and stronger race-outcome hits."""
    mean_err = float(delta.get("meanPositionError", 0.0) or 0.0)
    median_err = float(delta.get("medianPositionError", 0.0) or 0.0)
    winner_hit = float(delta.get("winnerHit", 0.0) or 0.0)
    podium = float(delta.get("podiumOverlap", 0.0) or 0.0)
    top10 = float(delta.get("top10Overlap", 0.0) or 0.0)
    within3 = float(delta.get("within3Pct", 0.0) or 0.0)

    return (
        -2.00 * mean_err
        -0.60 * median_err
        +1.20 * winner_hit
        +0.25 * podium
        +0.08 * top10
        +0.05 * within3
    )


def _run_and_eval(rounds, field_sims, neighbors, use_lstm, post_scale, unc_scale, baseline_agg):
    enhanced_rows, enhanced_agg = _run_variant(
        rounds,
        enable_game_theory=True,
        use_lstm=use_lstm,
        field_sims=field_sims,
        neighbors=neighbors,
        postprocess_scale=post_scale,
        uncertainty_scale=unc_scale,
    )
    delta = _diff(enhanced_agg, baseline_agg)
    score = _objective(delta)
    return {
        "postprocessScale": float(post_scale),
        "uncertaintyScale": float(unc_scale),
        "enhanced": {
            "perRound": enhanced_rows,
            "aggregate": enhanced_agg,
        },
        "deltaEnhancedMinusBaseline": delta,
        "objectiveScore": float(score),
    }


def main():
    parser = argparse.ArgumentParser(description="Optimize game-theory postprocessing scale")
    parser.add_argument("--rounds", nargs="+", type=int, default=[1, 2, 3],
                        help="Completed rounds to optimize against (default: 1 2 3)")
    parser.add_argument("--scales", type=str,
                        default="0.0,0.15,0.30,0.45,0.60,0.75,0.90,1.00,1.10,1.25",
                        help="Comma-separated postprocess scales to test")
    parser.add_argument("--uncertainty-scale", type=float, default=None,
                        help="Optional fixed uncertainty scale; default ties to each postprocess scale")
    parser.add_argument("--search-field-sims", type=int, default=180,
                        help="Field simulation count for search passes")
    parser.add_argument("--validate-field-sims", type=int, default=700,
                        help="Field simulation count for final validation pass (0 to skip)")
    parser.add_argument("--neighbors", type=int, default=2,
                        help="Nearest competitors used in field simulation")
    parser.add_argument("--use-lstm", action="store_true",
                        help="Enable LSTM for both baseline and enhanced variants")
    parser.add_argument("--output", type=str,
                        default=os.path.join("reports", "game_theory_postprocess_tuning.json"),
                        help="Path to write tuning report JSON")
    args = parser.parse_args()

    rounds = sorted(set(int(r) for r in args.rounds if int(r) > 0))
    scales = _parse_scale_list(args.scales)
    if not rounds:
        raise ValueError("No valid rounds provided")
    if not scales:
        raise ValueError("No valid scales provided")

    print(f"Tuning rounds: {rounds}")
    print(f"Scale candidates: {scales}")

    print("\nRunning baseline search pass...")
    baseline_rows_search, baseline_agg_search = _run_variant(
        rounds,
        enable_game_theory=False,
        use_lstm=args.use_lstm,
        field_sims=args.search_field_sims,
        neighbors=args.neighbors,
    )

    trials = []
    for scale in scales:
        unc_scale = args.uncertainty_scale if args.uncertainty_scale is not None else scale
        print(f"\nTrial scale={scale:.3f}, uncertainty={unc_scale:.3f}")
        trial = _run_and_eval(
            rounds,
            field_sims=args.search_field_sims,
            neighbors=args.neighbors,
            use_lstm=args.use_lstm,
            post_scale=scale,
            unc_scale=unc_scale,
            baseline_agg=baseline_agg_search,
        )
        delta = trial["deltaEnhancedMinusBaseline"]
        print(
            "  delta: "
            f"meanErr={delta.get('meanPositionError', 0.0):+.4f}, "
            f"medianErr={delta.get('medianPositionError', 0.0):+.4f}, "
            f"winner={delta.get('winnerHit', 0.0):+.4f}, "
            f"within3Pct={delta.get('within3Pct', 0.0):+.4f}, "
            f"score={trial['objectiveScore']:+.4f}"
        )
        trials.append(trial)

    trials.sort(key=lambda x: x["objectiveScore"], reverse=True)
    best = trials[0]

    print(
        "\nBest search candidate: "
        f"scale={best['postprocessScale']:.3f}, "
        f"uncertainty={best['uncertaintyScale']:.3f}, "
        f"score={best['objectiveScore']:+.4f}"
    )

    validation = None
    if int(args.validate_field_sims) > 0:
        print("\nRunning full validation pass...")
        baseline_rows_val, baseline_agg_val = _run_variant(
            rounds,
            enable_game_theory=False,
            use_lstm=args.use_lstm,
            field_sims=args.validate_field_sims,
            neighbors=args.neighbors,
        )
        enhanced_rows_val, enhanced_agg_val = _run_variant(
            rounds,
            enable_game_theory=True,
            use_lstm=args.use_lstm,
            field_sims=args.validate_field_sims,
            neighbors=args.neighbors,
            postprocess_scale=best["postprocessScale"],
            uncertainty_scale=best["uncertaintyScale"],
        )
        validation_delta = _diff(enhanced_agg_val, baseline_agg_val)
        validation = {
            "fieldSimulations": int(args.validate_field_sims),
            "baseline": {
                "perRound": baseline_rows_val,
                "aggregate": baseline_agg_val,
            },
            "enhanced": {
                "perRound": enhanced_rows_val,
                "aggregate": enhanced_agg_val,
            },
            "deltaEnhancedMinusBaseline": validation_delta,
            "objectiveScore": float(_objective(validation_delta)),
        }
        print(
            "Validation delta: "
            f"meanErr={validation_delta.get('meanPositionError', 0.0):+.4f}, "
            f"medianErr={validation_delta.get('medianPositionError', 0.0):+.4f}, "
            f"winner={validation_delta.get('winnerHit', 0.0):+.4f}, "
            f"within3Pct={validation_delta.get('within3Pct', 0.0):+.4f}"
        )

    payload = {
        "generatedAtUtc": datetime.utcnow().isoformat() + "Z",
        "rounds": rounds,
        "searchConfig": {
            "useLstm": bool(args.use_lstm),
            "fieldSimulations": int(args.search_field_sims),
            "nearestCompetitors": int(args.neighbors),
            "candidateScales": scales,
            "fixedUncertaintyScale": args.uncertainty_scale,
        },
        "searchBaseline": {
            "perRound": baseline_rows_search,
            "aggregate": baseline_agg_search,
        },
        "trials": trials,
        "bestSearchCandidate": {
            "postprocessScale": best["postprocessScale"],
            "uncertaintyScale": best["uncertaintyScale"],
            "objectiveScore": best["objectiveScore"],
            "deltaEnhancedMinusBaseline": best["deltaEnhancedMinusBaseline"],
        },
        "validation": validation,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nSaved tuning report to {args.output}")


if __name__ == "__main__":
    main()
