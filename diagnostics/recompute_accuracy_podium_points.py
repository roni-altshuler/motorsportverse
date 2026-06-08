#!/usr/bin/env python3
"""Republish rounds 1-6 under the podium-weighted accuracy definition.

Authorized production-data update. No re-prediction and no fabricated data — the
stored predicted/actual orders are untouched. Two legitimate changes:

  1. Accuracy is recomputed with the new headline metric: a podium-weighted blend
     (60% podium, 40% points) of how often the right drivers are classified into
     the top 3 / top 10 (advanced_models.podium_points_accuracy). The legacy
     within-3 figure is preserved as a detail stat.
  2. Any concluded round whose weekend "Grand Prix Result" session is empty is
     backfilled from the official classified results so the page stops showing
     "Awaiting data" (the Monaco/R6 symptom).

Rebuilds season_tracker(_2026).json + gp_accuracy_report.json and writes the
recomputed accuracy back into each round file.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("F1_REGISTRY_ENABLED", "0")
os.environ.setdefault("F1_USE_LIVE_STANDINGS", "0")
os.environ.setdefault("F1_USE_LIVE_ROUND_RESULTS", "0")

import export_website_data as ew  # noqa: E402
from advanced_models import SeasonTracker  # noqa: E402

ROUNDS_DIR = "website/public/data/rounds"
COMPLETED_ROUNDS = range(1, 7)  # rounds 1..6 carry actual results


def load_round(r):
    with open(f"{ROUNDS_DIR}/round_{r:02d}.json") as f:
        return json.load(f)


def write_round(r, data):
    with open(f"{ROUNDS_DIR}/round_{r:02d}.json", "w") as f:
        json.dump(data, f, indent=2)


def main():
    # 1. Backfill any empty race session from the official classified results.
    for r in COMPLETED_ROUNDS:
        data = load_round(r)
        if ew._backfill_race_session_from_actual(data):
            write_round(r, data)
            print(f"  R{r}: backfilled Grand Prix Result session from actualResults")

    # 2. Recompute accuracy from stored predicted/actual with the new formula.
    tracker = SeasonTracker()
    tracker.sync_from_round_directory(ROUNDS_DIR)
    tracker.save()  # season_tracker_2026.json
    export = tracker.export_for_website()
    with open("website/public/data/season_tracker.json", "w") as f:
        json.dump(export, f, indent=2)
    ew._write_gp_accuracy_report(export)

    # 3. Write the tracker-computed accuracy back into each round file.
    for r in COMPLETED_ROUNDS:
        acc = tracker.data["accuracy"].get(str(r))
        if acc:
            data = load_round(r)
            data["accuracy"] = acc
            write_round(r, data)

    print("\nSeason accuracy (podium-weighted blend):")
    print(" ", json.dumps(export["overallAccuracy"], indent=2))
    print("\nPer-round:")
    for row in export["rounds"]:
        if not row.get("hasActual"):
            continue
        print(f"  R{row['round']:<2} headline={row['accuracyPct']}%  "
              f"podium={row.get('podiumAccuracyPct')}%  points={row.get('pointsAccuracyPct')}%  "
              f"within3(all)={row.get('within3AccuracyPct')}%")


if __name__ == "__main__":
    main()
