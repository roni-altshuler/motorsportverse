#!/usr/bin/env python3
"""Retroactive, leakage-safe regeneration of post-qualifying predictions.

Why this exists (forensic audit, 2026-07-07): six of the nine completed 2026
rounds never received a genuine real-grid post-qualifying prediction — R1-5
froze on *estimated* qualifying times (guard bug fixed in 6e46b2f), and R9
froze pre-qualifying on the wrong race's grid (09d607f incident). The one-shot
freeze gate could never self-correct, so the season's scored predictions
misrepresent what the model can do post-quali. This script replays every
completed round as an honest post-qualifying freeze.

Leakage contract (walk-forward): for round N the pipeline sees
  * all data through round N-1 (predicted + actual position maps, Elo replay,
    bias features — all filtered by ``current_round=N`` and enforced with
    ``assert_prior_only`` at the boundaries in f1_prediction_utils), plus
  * round N's REAL qualifying results (times + official grid) — data that is
    available the moment qualifying ends, before the race,
  * NEVER round N's race outcome. Race actuals only re-enter after the
    prediction is built, as display fields (``actualResults``/``accuracy``).

Qualifying data source: the committed ``round_NN.json::weekendResults``
qualifying session (official, round-scoped by construction — originally
ingested from Jolpica with round-echo guards). It is injected via
``f1_prediction_utils.set_qualifying_override`` so the replay is deterministic
and offline-safe; when a round has no committed qualifying session the network
fetch (with the wrong-event round guard) is the fallback.

Environment forced by this script:
  * ``F1_REGISTRY_ENABLED=0`` — the online game-theory coefficients (registry
    sentinel 98) were learned through R9 and would leak backwards; disabling
    the registry falls back to the static legacy coefficients and also
    protects the committed registry metadata.
  * ``OMP_NUM_THREADS=1`` — xgboost hangs under parallel load in this env.

The previous published state is archived to
``website/public/data/archive/pre-overhaul/`` before anything is overwritten.

Usage::

    python src/regenerate_post_quali.py                    # all completed rounds
    python src/regenerate_post_quali.py --rounds 1-5
    python src/regenerate_post_quali.py --skip-archive     # archive already taken
    python src/regenerate_post_quali.py --candidate --output-predictions \
        website/public/data/forward_eval_candidate/predicted_results.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

# Must be set before xgboost/numpy import anywhere downstream.
os.environ.setdefault("OMP_NUM_THREADS", "1")
# Block backward leakage from registry state learned later in the season and
# protect committed registry metadata. Set BEFORE importing pipeline modules.
os.environ["F1_REGISTRY_ENABLED"] = "0"

sys.path.insert(0, os.path.dirname(__file__))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# models/ and features/ are importable packages at the project root.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
DATA_DIR = os.path.join(PROJECT_ROOT, "website", "public", "data")
ROUNDS_DIR = os.path.join(DATA_DIR, "rounds")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive", "pre-overhaul")


def _load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _parse_rounds(spec):
    if not spec:
        return None
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return sorted(out)


def completed_rounds(season_year):
    """Rounds with official results — the replay set."""
    results = _load_json(os.path.join(DATA_DIR, f"season_results_{season_year}.json")) or {}
    return sorted(int(r) for r in results)


def archive_previous_state(season_year, force=False):
    """Snapshot the current published JSONs so the overhaul is reviewable."""
    if os.path.isdir(ARCHIVE_DIR) and os.listdir(ARCHIVE_DIR) and not force:
        print(f"📦 Archive already exists at {ARCHIVE_DIR} — keeping it (use --force-archive to redo).")
        return False
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    dirs = ["rounds", "forward_eval", "probabilities"]
    files = [
        f"predicted_results_{season_year}.json",
        f"season_results_{season_year}.json",
        "season_tracker.json",
        "gp_accuracy_report.json",
    ]
    for name in dirs:
        src = os.path.join(DATA_DIR, name)
        dst = os.path.join(ARCHIVE_DIR, name)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
    for name in files:
        src = os.path.join(DATA_DIR, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ARCHIVE_DIR, name))
    # Project-root state twins (tracker + predicted results feed the features).
    for name in (f"predicted_results_{season_year}.json", f"season_tracker_{season_year}.json"):
        src = os.path.join(PROJECT_ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ARCHIVE_DIR, f"project_root__{name}"))
    print(f"📦 Archived previous published state → {ARCHIVE_DIR}")
    return True


def inject_committed_qualifying(round_num, season_year, rounds_source_dir=None):
    """Seed the qualifying override from the committed official session.

    Returns True when an override was injected. The committed weekendResults
    qualifying session is round-scoped by construction, so this can never
    inject a wrong-event grid.
    """
    from f1_prediction_utils import (
        CALENDAR, set_qualifying_override, _parse_laptime_to_seconds,
    )

    source_dir = rounds_source_dir or ROUNDS_DIR
    payload = _load_json(os.path.join(source_dir, f"round_{round_num:02d}.json")) or {}
    if int(payload.get("round", -1) or -1) != int(round_num):
        return False
    session = next(
        (s for s in (payload.get("weekendResults") or {}).get("sessions", [])
         if s.get("key") == "qualifying" and s.get("rows")),
        None,
    )
    if session is None:
        return False

    times, grid = {}, {}
    for row in session["rows"]:
        drv = row.get("driver")
        if not drv:
            continue
        try:
            grid[drv] = int(row["position"])
        except (KeyError, TypeError, ValueError):
            pass
        best = [
            _parse_laptime_to_seconds(row.get(key))
            for key in ("q3", "q2", "q1")
        ]
        best = [t for t in best if t is not None]
        if best:
            times[drv] = min(best)

    if not times:
        return False
    gp_key = CALENDAR[round_num]["gp_key"]
    set_qualifying_override(season_year, gp_key, times, grid=grid)
    print(f"  🏁 Injected committed official qualifying for round {round_num} "
          f"({len(times)} timed drivers, grid of {len(grid)}).")
    return True


def regenerate_round(round_num, season_year, *, persist=True,
                     rounds_source_dir=None, use_race_simulator=False):
    """Replay one round as an honest post-quali freeze; return the round payload."""
    from f1_prediction_utils import clear_qualifying_overrides
    from export_website_data import export_round_data

    os.environ["F1_CURRENT_ROUND"] = str(round_num)
    clear_qualifying_overrides()
    injected = inject_committed_qualifying(round_num, season_year,
                                           rounds_source_dir=rounds_source_dir)
    if not injected:
        print(f"  ⚠️  Round {round_num}: no committed qualifying session — "
              "falling back to the round-verified network fetch.")

    round_data = export_round_data(
        round_num,
        return_merged=False,
        use_lstm=True,            # degrades gracefully without torch
        use_weather_api=False,    # deterministic climatological priors
        use_telemetry=False,      # display-only data; avoids FastF1 rate limit
        use_race_simulator=use_race_simulator,
        persist_output=persist,
        generate_visualizations=persist,
        prediction_phase="post-quali",
    )
    provenance = round_data.get("gridProvenance")
    if provenance != "real-quali-verified":
        raise RuntimeError(
            f"Round {round_num} regenerated with gridProvenance={provenance!r} — "
            "refusing to publish a non-verified retroactive freeze."
        )
    return round_data


def _predicted_map(round_data):
    out = {}
    for entry in round_data.get("classification", []):
        try:
            out[str(entry["driver"])] = int(entry["position"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=str, default=None,
                        help="Round filter, e.g. '1-9' or '3,5'. Default: all completed.")
    parser.add_argument("--skip-archive", action="store_true",
                        help="Do not (re)take the pre-overhaul archive.")
    parser.add_argument("--force-archive", action="store_true",
                        help="Overwrite an existing archive snapshot.")
    parser.add_argument("--candidate", action="store_true",
                        help="Candidate stream: sets F1_CANDIDATE_MODEL=1, does NOT "
                             "touch the published round JSONs/tracker, and writes the "
                             "walk-forward predictions to --output-predictions.")
    parser.add_argument("--output-predictions", type=str, default=None,
                        help="Where to write the {round: {driver: pos}} map "
                             "(candidate mode default: website/public/data/"
                             "forward_eval_candidate/predicted_results.json).")
    parser.add_argument("--use-race-simulator", action="store_true")
    args = parser.parse_args()

    if args.candidate:
        os.environ["F1_CANDIDATE_MODEL"] = "1"

    # Import AFTER env vars are pinned.
    from f1_prediction_utils import SEASON_YEAR
    season_year = int(SEASON_YEAR)

    rounds = _parse_rounds(args.rounds) or completed_rounds(season_year)
    if not rounds:
        print("Nothing to regenerate — no completed rounds found.")
        return 0

    persist = not args.candidate
    rounds_source_dir = ROUNDS_DIR

    if persist and not args.skip_archive:
        archive_previous_state(season_year, force=args.force_archive)
        # Once archived, the committed quali sessions are read from the archive
        # so a partially-regenerated tree can be safely re-run.
        if os.path.isdir(os.path.join(ARCHIVE_DIR, "rounds")):
            rounds_source_dir = os.path.join(ARCHIVE_DIR, "rounds")
    elif persist and os.path.isdir(os.path.join(ARCHIVE_DIR, "rounds")):
        rounds_source_dir = os.path.join(ARCHIVE_DIR, "rounds")

    # Candidate mode must not pollute the published walk-forward state files:
    # save_predicted_result() writes predicted_results_<year>.json even when
    # persist_output=False (it is what makes the walk self-consistent), so we
    # snapshot + restore around the loop.
    snapshots = {}
    if args.candidate:
        for path in (
            os.path.join(PROJECT_ROOT, f"predicted_results_{season_year}.json"),
            os.path.join(DATA_DIR, f"predicted_results_{season_year}.json"),
        ):
            snapshots[path] = open(path).read() if os.path.exists(path) else None
        # Start the candidate walk from a clean slate so round N's bias
        # features see the CANDIDATE's rounds <N, not production's.
        for path in snapshots:
            if os.path.exists(path):
                os.remove(path)

    predictions = {}
    failures = []
    try:
        for rnd in sorted(rounds):
            print(f"\n{'█' * 70}\n  REGENERATING ROUND {rnd} "
                  f"({'candidate' if args.candidate else 'production'} stream)\n{'█' * 70}")
            try:
                round_data = regenerate_round(
                    rnd, season_year, persist=persist,
                    rounds_source_dir=rounds_source_dir,
                    use_race_simulator=args.use_race_simulator,
                )
                predictions[str(rnd)] = _predicted_map(round_data)
            except Exception as exc:
                failures.append((rnd, str(exc)))
                print(f"  ❌ Round {rnd} failed: {exc}")
    finally:
        if args.candidate:
            for path, content in snapshots.items():
                if content is None:
                    if os.path.exists(path):
                        os.remove(path)
                else:
                    with open(path, "w") as fh:
                        fh.write(content)

    out_path = args.output_predictions
    if args.candidate and not out_path:
        out_path = os.path.join(DATA_DIR, "forward_eval_candidate", "predicted_results.json")
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(predictions, fh, indent=2)
        print(f"\n💾 Walk-forward predictions → {out_path}")

    print(f"\n{'=' * 70}\n  REGENERATION COMPLETE: {len(predictions)} round(s) OK, "
          f"{len(failures)} failed\n{'=' * 70}")
    for rnd, msg in failures:
        print(f"  ❌ R{rnd}: {msg}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
