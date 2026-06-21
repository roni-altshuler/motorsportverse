#!/usr/bin/env python3
"""Sandboxed re-run of the CURRENT model for completed rounds 1-5.

Safety (see plans/we-have-reached-a-reactive-river.md):
  * persist_output=False, generate_visualizations=False  -> no website/viz writes
  * F1_REGISTRY_ENABLED=0                                 -> registry save no-ops
  * save_predicted_result monkeypatched to no-op          -> protects predicted_results_2026.json
  * use_weather_api=False, use_telemetry=False            -> offline; cached quali/race only
  * F1_USE_LIVE_STANDINGS=0, F1_USE_LIVE_ROUND_RESULTS=0  -> no network

Writes ONLY under diagnostics/rebuild_2026/.

Variants:
  (a) frozen : prior-round feedback features read the committed predicted/season results.
               Isolates code-vs-data ("what current code outputs given frozen history").
  (b) rechain: PREDICTED_RESULTS_FILE redirected to a scratch file that accumulates the
               rebuilt predictions round-by-round ("what current code produces from scratch").
"""
import os
import sys
import json
import argparse

os.environ.setdefault("F1_REGISTRY_ENABLED", "0")
os.environ.setdefault("F1_USE_LIVE_STANDINGS", "0")
os.environ.setdefault("F1_USE_LIVE_ROUND_RESULTS", "0")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join(HERE, "rebuild_2026")
ROUNDS_OUT = os.path.join(OUT, "rounds")
os.makedirs(ROUNDS_OUT, exist_ok=True)

import export_website_data as ew          # noqa: E402
import f1_prediction_utils as fpu         # noqa: E402

# Neutralize the one destructive write persist_output does not guard.
ew.save_predicted_result = lambda *a, **k: None
fpu.save_predicted_result = lambda *a, **k: None


def positions_from_round(round_data):
    return {c["driver"]: int(c["position"]) for c in round_data["classification"]}


def run(variant, rounds):
    predicted_map = {}
    scratch_pred_file = os.path.join(OUT, f"predicted_chain_{variant}.json")

    if variant == "rechain":
        # Redirect the predicted-results source the feature loaders read from.
        with open(scratch_pred_file, "w") as f:
            json.dump({}, f)
        fpu.PREDICTED_RESULTS_FILE = scratch_pred_file
        fpu.PREDICTED_RESULTS_WEBSITE_FILE = scratch_pred_file

    for r in rounds:
        print(f"\n=== [{variant}] Rebuilding round {r} ===", flush=True)
        round_data, _merged = ew.export_round_data(
            r,
            return_merged=True,
            use_lstm=False,
            use_weather_api=False,
            use_telemetry=False,
            enable_game_theory=True,
            persist_output=False,
            generate_visualizations=False,
            use_race_simulator=False,
            prediction_phase="diagnostic",
        )
        with open(os.path.join(ROUNDS_OUT, f"round_{r:02d}_{variant}.json"), "w") as f:
            json.dump(round_data, f, indent=2)
        pos = positions_from_round(round_data)
        predicted_map[str(r)] = pos

        if variant == "rechain":
            # Append this round so the NEXT round's features read it back.
            chain = json.load(open(scratch_pred_file))
            chain[str(r)] = pos
            with open(scratch_pred_file, "w") as f:
                json.dump(chain, f, indent=2)

    out_path = os.path.join(OUT, f"predicted_rebuilt_{variant}_2026.json")
    with open(out_path, "w") as f:
        json.dump(predicted_map, f, indent=2)
    print(f"\nWrote {out_path}")
    return predicted_map


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["frozen", "rechain"], default="frozen")
    ap.add_argument("--rounds", default="1,2,3,4,5")
    args = ap.parse_args()
    rounds = [int(x) for x in args.rounds.split(",") if x.strip()]
    run(args.variant, rounds)
