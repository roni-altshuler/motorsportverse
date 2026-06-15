#!/usr/bin/env python3
"""Benchmark current vs game-theory-enhanced model on completed rounds."""

import argparse
import json
import os
from statistics import mean, median

from export_website_data import export_round_data


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDICTION_STATE_FILES = [
    os.path.join(PROJECT_ROOT, "predicted_results_2026.json"),
    os.path.join(PROJECT_ROOT, "website", "public", "data", "predicted_results_2026.json"),
]


def _snapshot_file(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def _restore_file(path, payload):
    if payload is None:
        if os.path.exists(path):
            os.remove(path)
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(payload)


def _classification_to_map(classification_rows):
    out = {}
    for row in classification_rows:
        try:
            out[str(row["driver"])] = int(row["position"])
        except Exception:
            continue
    return out


def _actual_to_map(round_data):
    actual = round_data.get("actualResults")
    if not isinstance(actual, dict):
        return {}
    out = {}
    for drv, pos in actual.items():
        try:
            out[str(drv)] = int(pos)
        except Exception:
            continue
    return out


def _compute_metrics(predicted_map, actual_map):
    common = sorted(set(predicted_map.keys()) & set(actual_map.keys()))
    if not common:
        return {
            "driversCompared": 0,
            "meanPositionError": None,
            "medianPositionError": None,
            "winnerHit": 0,
            "podiumOverlap": 0,
            "top10Overlap": 0,
            "within3Count": 0,
            "within3Pct": 0.0,
        }

    diffs = [abs(predicted_map[d] - actual_map[d]) for d in common]

    pred_sorted = sorted(predicted_map.items(), key=lambda kv: kv[1])
    act_sorted = sorted(actual_map.items(), key=lambda kv: kv[1])
    pred_top3 = {d for d, _ in pred_sorted[:3]}
    act_top3 = {d for d, _ in act_sorted[:3]}
    pred_top10 = {d for d, _ in pred_sorted[:10]}
    act_top10 = {d for d, _ in act_sorted[:10]}

    winner_hit = int(bool(pred_sorted and act_sorted and pred_sorted[0][0] == act_sorted[0][0]))
    within3 = sum(1 for x in diffs if x <= 3)

    return {
        "driversCompared": len(common),
        "meanPositionError": float(mean(diffs)),
        "medianPositionError": float(median(diffs)),
        "winnerHit": winner_hit,
        "podiumOverlap": int(len(pred_top3 & act_top3)),
        "top10Overlap": int(len(pred_top10 & act_top10)),
        "within3Count": int(within3),
        "within3Pct": float(within3 / len(common) * 100.0),
    }


def _aggregate(round_rows):
    if not round_rows:
        return {}

    numeric_keys = [
        "meanPositionError",
        "medianPositionError",
        "winnerHit",
        "podiumOverlap",
        "top10Overlap",
        "within3Count",
        "within3Pct",
        "driversCompared",
    ]
    out = {}
    for key in numeric_keys:
        vals = [r[key] for r in round_rows if r.get(key) is not None]
        out[key] = float(mean(vals)) if vals else None
    return out


def _run_variant(
    rounds,
    enable_game_theory,
    use_lstm=False,
    field_sims=700,
    neighbors=2,
    postprocess_scale=None,
    uncertainty_scale=None,
):
    old_postprocess_scale = os.getenv("F1_GAME_THEORY_POSTPROCESS_SCALE")
    old_uncertainty_scale = os.getenv("F1_GAME_THEORY_UNCERTAINTY_SCALE")
    snapshots = {path: _snapshot_file(path) for path in PREDICTION_STATE_FILES}

    if postprocess_scale is not None:
        os.environ["F1_GAME_THEORY_POSTPROCESS_SCALE"] = f"{float(postprocess_scale):.6g}"
    if uncertainty_scale is not None:
        os.environ["F1_GAME_THEORY_UNCERTAINTY_SCALE"] = f"{float(uncertainty_scale):.6g}"

    rows = []
    try:
        for rnd in rounds:
            round_data, _ = export_round_data(
                rnd,
                return_merged=True,
                use_lstm=use_lstm,
                use_weather_api=False,
                use_telemetry=False,
                enable_game_theory=enable_game_theory,
                game_theory_field_sims=field_sims,
                game_theory_neighbors=neighbors,
                persist_output=False,
                generate_visualizations=False,
            )

            predicted_map = _classification_to_map(round_data.get("classification", []))
            actual_map = _actual_to_map(round_data)
            metrics = _compute_metrics(predicted_map, actual_map)
            metrics["round"] = int(rnd)
            metrics["name"] = round_data.get("name", f"Round {rnd}")
            rows.append(metrics)
    finally:
        if postprocess_scale is not None:
            if old_postprocess_scale is None:
                os.environ.pop("F1_GAME_THEORY_POSTPROCESS_SCALE", None)
            else:
                os.environ["F1_GAME_THEORY_POSTPROCESS_SCALE"] = old_postprocess_scale
        if uncertainty_scale is not None:
            if old_uncertainty_scale is None:
                os.environ.pop("F1_GAME_THEORY_UNCERTAINTY_SCALE", None)
            else:
                os.environ["F1_GAME_THEORY_UNCERTAINTY_SCALE"] = old_uncertainty_scale
        for path, payload in snapshots.items():
            _restore_file(path, payload)

    return rows, _aggregate(rows)


def _diff(enhanced, baseline):
    keys = sorted(set(enhanced.keys()) & set(baseline.keys()))
    out = {}
    for key in keys:
        if enhanced[key] is None or baseline[key] is None:
            out[key] = None
        else:
            out[key] = float(enhanced[key] - baseline[key])
    return out


def _print_table(title, rows):
    print(f"\n{title}")
    print("-" * len(title))
    header = (
        f"{'Round':>5}  {'Winner':>6}  {'Podium':>6}  {'Top10':>5}  "
        f"{'Within3%':>8}  {'MeanErr':>8}  {'MedianErr':>9}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['round']:>5}  {r['winnerHit']:>6}  {r['podiumOverlap']:>6}  {r['top10Overlap']:>5}  "
            f"{r['within3Pct']:>8.2f}  {r['meanPositionError']:>8.3f}  {r['medianPositionError']:>9.3f}"
        )


def main():
    parser = argparse.ArgumentParser(description="Benchmark game-theory upgrades on completed rounds")
    parser.add_argument("--rounds", nargs="+", type=int, default=[1, 2, 3],
                        help="Rounds to evaluate (default: 1 2 3)")
    parser.add_argument("--field-sims", type=int, default=700,
                        help="Field simulation count for enhanced variant")
    parser.add_argument("--neighbors", type=int, default=2,
                        help="Nearest competitors used by enhanced variant")
    parser.add_argument("--use-lstm", action="store_true",
                        help="Enable LSTM for both variants")
    parser.add_argument("--postprocess-scale", type=float, default=None,
                        help="Scale game-theory postprocessing contribution for enhanced variant")
    parser.add_argument("--uncertainty-scale", type=float, default=None,
                        help="Scale game-theory uncertainty contribution for enhanced variant")
    parser.add_argument("--output", type=str,
                        default=os.path.join("reports", "game_theory_benchmark_rounds_1_3.json"),
                        help="Path to save benchmark JSON report")
    args = parser.parse_args()

    rounds = sorted(set(int(r) for r in args.rounds if int(r) > 0))
    print(f"Evaluating rounds: {rounds}")

    baseline_rows, baseline_agg = _run_variant(
        rounds,
        enable_game_theory=False,
        use_lstm=args.use_lstm,
        field_sims=args.field_sims,
        neighbors=args.neighbors,
    )
    enhanced_rows, enhanced_agg = _run_variant(
        rounds,
        enable_game_theory=True,
        use_lstm=args.use_lstm,
        field_sims=args.field_sims,
        neighbors=args.neighbors,
        postprocess_scale=args.postprocess_scale,
        uncertainty_scale=args.uncertainty_scale,
    )

    _print_table("Baseline (Current Model)", baseline_rows)
    _print_table("Enhanced (5 Upgrades)", enhanced_rows)

    aggregate_delta = _diff(enhanced_agg, baseline_agg)
    print("\nAggregate Comparison (Enhanced - Baseline)")
    print("------------------------------------------")
    for key in [
        "winnerHit",
        "podiumOverlap",
        "top10Overlap",
        "within3Pct",
        "meanPositionError",
        "medianPositionError",
    ]:
        val = aggregate_delta.get(key)
        if val is None:
            continue
        print(f"{key}: {val:+.4f}")

    payload = {
        "rounds": rounds,
        "config": {
            "useLstm": bool(args.use_lstm),
            "fieldSimulations": int(args.field_sims),
            "nearestCompetitors": int(args.neighbors),
            "postprocessScale": args.postprocess_scale,
            "uncertaintyScale": args.uncertainty_scale,
        },
        "baseline": {
            "perRound": baseline_rows,
            "aggregate": baseline_agg,
        },
        "enhanced": {
            "perRound": enhanced_rows,
            "aggregate": enhanced_agg,
        },
        "deltaEnhancedMinusBaseline": aggregate_delta,
    }

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved benchmark report to {args.output}")


if __name__ == "__main__":
    main()
