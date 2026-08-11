"""Refresh the committed IMSA WeatherTech snapshot, then re-export the website data.

Two steps, in order:

1. **Re-pull** (network) the current season from the official Al Kamel timing
   archive via the committed ingester (:mod:`imsa_predictions.build_snapshot`),
   guarded so that offline / CI is a **graceful no-op**: any failure (no network,
   archive down, import error) leaves the committed ``data/official_<season>.json``
   untouched — a flaky source must never corrupt committed data. A refresh can only
   ever *add* completed rounds: it refuses to overwrite a healthy snapshot with one
   that has FEWER completed rounds (the freshness/regression guard that protects
   every series against a transient empty scrape wiping real data). Entry **codes**
   are ``<CLASS_TAG>-<number>`` so a car keeps a stable identity; the wrong-event
   guard is inherent (each round is keyed by its Al Kamel event folder, and rounds
   are renumbered only from events that yield a real WeatherTech classification).

2. **Re-export** the website JSON + forward-eval from whatever snapshot is now on
   disk. IMPORTANT: :mod:`imsa_predictions.config` resolves the active season (and
   the completed-round count) **at import time**, so a fetch that ADDED rounds is
   only visible to a *fresh* process. This module therefore runs
   :mod:`imsa_predictions.export` and :mod:`imsa_predictions.forward_eval` as
   **separate Python subprocesses** after the snapshot is rebuilt — each re-resolves
   ``config`` against the freshly written snapshot.

Because step 1 is fully guarded, running this offline simply re-exports the
committed snapshot — the deterministic, reproducible path CI and local dev use.

Run:  PYTHONPATH=src python -m imsa_predictions.refresh [--season 2026]
          [--no-fetch] [--skip-forward-eval] [--allow-regression]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import config

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _existing_completed(path: Path, season: int) -> int:
    """completedRounds in the snapshot already on disk (0 if absent/unreadable)."""
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        if cur.get("season") != season:
            return 0
        return len(cur.get("completedRounds") or [])
    except Exception:
        return 0


def refresh_snapshot(season: int, *, allow_regression: bool = False) -> bool:
    """Guarded network re-pull of the current-season snapshot. Returns True if the
    committed snapshot was updated, False on any offline/no-op path.

    Never raises: a failed fetch keeps the committed snapshot and returns False.
    """
    out_path = _DATA_DIR / f"official_{season}.json"
    try:
        from motorsport_data.sources.alkamel import AlKamelClient

        from .build_snapshot import _CHAMP_HINT, _HOST, build_season

        client = AlKamelClient(_HOST, _CHAMP_HINT, _DATA_DIR / ".http_cache")
        folder_for = {y: sf for sf, y in client.list_seasons()}
        season_folder = folder_for.get(season)
        if not season_folder:
            print(f"refresh: no {season} season folder in the archive; keeping the committed snapshot.")
            return False
        snap = build_season(client, season_folder, season)
    except Exception as exc:  # offline / network / API change → keep committed snapshot
        print(f"refresh: snapshot re-pull skipped ({type(exc).__name__}: {exc}); "
              "keeping the committed snapshot.")
        return False

    fresh = len(snap.get("completedRounds") or [])
    existing = _existing_completed(out_path, season)
    if fresh < existing and not allow_regression:
        print(f"refresh: re-pull produced {fresh} completed round(s) but the committed "
              f"snapshot has {existing} — refusing to regress. Use --allow-regression to override.")
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"refresh: wrote {out_path} — {fresh}/{snap.get('totalRounds')} rounds, "
          f"{len(snap.get('entries', []))} entries, classes={snap.get('classes')}.")
    return True


def _run_module(module: str, args: list[str], season: int) -> int:
    """Run ``python -m <module> <args>`` in a fresh process so its module-level
    ``config`` re-resolves against the snapshot on disk. ``IMSA_SEASON_YEAR`` pins the
    season the child resolves to; PYTHONPATH is inherited from this process."""
    env = dict(os.environ)
    env["IMSA_SEASON_YEAR"] = str(season)
    cmd = [sys.executable, "-m", module, *args]
    print(f"refresh: running {' '.join(cmd)}")
    return subprocess.run(cmd, env=env, check=False).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, default=config.SEASON)
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip the network re-pull; just re-export the committed snapshot")
    ap.add_argument("--skip-forward-eval", action="store_true",
                    help="skip the walk-forward evaluation / model_health step")
    ap.add_argument("--allow-regression", action="store_true",
                    help="permit overwriting the snapshot with FEWER completed rounds")
    args = ap.parse_args()

    if not args.no_fetch:
        refresh_snapshot(args.season, allow_regression=args.allow_regression)
    else:
        print("refresh: --no-fetch → re-exporting the committed snapshot.")

    # Export and forward_eval run as SEPARATE processes so the module-level config
    # re-resolves against the (possibly just-rebuilt) snapshot on disk.
    rc = _run_module("imsa_predictions.export", [], args.season)
    if rc != 0:
        print(f"refresh: export exited {rc}", flush=True)
        return rc

    if not args.skip_forward_eval:
        rc = _run_module(
            "imsa_predictions.forward_eval", ["--season", str(args.season), "--allow-empty"],
            args.season,
        )
        if rc != 0:
            print(f"refresh: forward_eval exited {rc}", flush=True)
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
