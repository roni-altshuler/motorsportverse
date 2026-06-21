#!/usr/bin/env python3
"""Regenerate the published rounds 1-5 with honest, up-to-date numbers.

Authorized production-data update (the user asked for the site to reflect the
re-run/analysis). Three legitimate changes — no fabricated accuracy:

  1. R1 prediction re-run with the P1 qualifying-NaN fix (genuine improvement:
     SAI/STR no longer predicted P1/P2). Actual results unchanged.
  2. Accuracy-among-classified-finishers added to every round (DNF/DNS excluded,
     shown ALONGSIDE the raw number — a fair measure of pace-forecast skill).
  3. circuitVolatility (expected deviation / SC risk) attached per round.

Also backfills R4 `actualStatus` (was empty) from FastF1 so its finisher metric
is correct. Rebuilds season_tracker + gp_accuracy_report from the round files.
"""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("F1_REGISTRY_ENABLED", "0")
os.environ.setdefault("F1_USE_LIVE_STANDINGS", "0")
os.environ.setdefault("F1_USE_LIVE_ROUND_RESULTS", "0")
logging.getLogger("fastf1").setLevel(logging.ERROR)

import fastf1  # noqa: E402
import export_website_data as ew  # noqa: E402
import f1_prediction_utils as fpu  # noqa: E402
from advanced_models import SeasonTracker  # noqa: E402
from models.race_volatility import circuit_volatility  # noqa: E402

fastf1.Cache.enable_cache("f1_cache")
GP = {1: "Australia", 2: "China", 3: "Japan", 4: "Miami", 5: "Canada"}
ROUNDS_DIR = "website/public/data/rounds"
ew.save_predicted_result = lambda *a, **k: None      # never prune predicted_results
fpu.save_predicted_result = lambda *a, **k: None


def load_round(r):
    with open(f"{ROUNDS_DIR}/round_{r:02d}.json") as f:
        return json.load(f)


def write_round(r, data):
    with open(f"{ROUNDS_DIR}/round_{r:02d}.json", "w") as f:
        json.dump(data, f, indent=2)


def backfill_status(data, gp_key):
    """Ensure actualStatus is present; derive from FastF1 race Status if empty."""
    if data.get("actualStatus"):
        return data
    s = fastf1.get_session(2026, gp_key, "R")
    s.load(laps=False, telemetry=False, weather=False, messages=False)
    status = {}
    for _, row in s.results.iterrows():
        drv = str(row["Abbreviation"])
        finished = (str(row["Status"]) == "Finished" or "Lap" in str(row["Status"]))
        pos = data.get("actualResults", {}).get(drv)
        status[drv] = str(pos) if (finished and pos is not None) else "R"
    data["actualStatus"] = status
    print(f"  backfilled actualStatus for {gp_key} ({sum(1 for v in status.values() if not v.isdigit())} DNF)")
    return data


def regen_round1():
    """Re-predict R1 with the fixed model; keep all post-race fields."""
    print("R1: re-running prediction with P1 qualifying fix …")
    fresh, _ = ew.export_round_data(
        1, return_merged=True, use_weather_api=False, use_telemetry=False,
        persist_output=False, generate_visualizations=False,
        prediction_phase="post-race")
    existing = load_round(1)
    existing["classification"] = fresh["classification"]
    for k in ("podium", "fastestLap"):
        if k in fresh:
            existing[k] = fresh[k]
    write_round(1, existing)
    # Update predicted_results (R1 only) without pruning other rounds.
    newpos = {c["driver"]: int(c["position"]) for c in fresh["classification"]}
    for path in ("predicted_results_2026.json",
                 "website/public/data/predicted_results_2026.json"):
        d = json.load(open(path))
        d["1"] = newpos
        json.dump({k: d[k] for k in sorted(d, key=int)}, open(path, "w"), indent=2)
    top3 = [c["driver"] for c in sorted(fresh["classification"], key=lambda x: x["position"])[:3]]
    print(f"  R1 new predicted podium: {top3}")


def main():
    regen_round1()
    # Attach volatility + ensure status on every round.
    for r in range(1, 6):
        data = load_round(r)
        data = backfill_status(data, GP[r])
        data["circuitVolatility"] = circuit_volatility(GP[r]).as_dict()
        write_round(r, data)

    # Rebuild tracker (computes raw + classified accuracy) and republish.
    tracker = SeasonTracker()
    tracker.sync_from_round_directory(ROUNDS_DIR)
    tracker.save()                                   # season_tracker_2026.json
    export = tracker.export_for_website()
    with open("website/public/data/season_tracker.json", "w") as f:
        json.dump(export, f, indent=2)
    ew._write_gp_accuracy_report(export)

    # Write tracker-computed accuracy back into each round file (single source).
    for r in range(1, 6):
        acc = tracker.data["accuracy"].get(str(r))
        if acc:
            data = load_round(r)
            data["accuracy"] = acc
            write_round(r, data)

    print("\nOverall accuracy (raw vs classified-finishers):")
    print(" ", json.dumps(export["overallAccuracy"], indent=2))
    print("\nPer-round:")
    for row in export["rounds"]:
        print(f"  R{row['round']} {GP.get(row['round'],''):<10} "
              f"within3 raw={row['accuracyPct']}%  classified={row.get('accuracyPctClassified')}%  "
              f"meanErr {row['meanError']}->{row.get('meanErrorClassified')}  dnf={row.get('dnfCount')}")


if __name__ == "__main__":
    main()
