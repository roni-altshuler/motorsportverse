"""Refresh the committed WRC snapshot, then re-export the website data.

Two steps, in order:

1. **Re-pull** (network) the current season from the official wrc.com results API
   via the committed ingester (:mod:`wrc_predictions.build_snapshot`), guarded so
   that offline / CI is a **graceful no-op**: any failure (no network, API down,
   import error) leaves the committed ``data/official_<season>.json`` untouched. A
   refresh can only ever *add* completed rounds — it refuses to overwrite a healthy
   snapshot with one that has FEWER completed rounds (the freshness/regression guard
   that protects every series against a transient empty scrape wiping real data).
   Driver **codes** are assigned over the same season range the committed snapshots
   used, so a crew keeps a stable code. The wrong-event guard is inherent: the API
   keys every round by ``eventId``, so a round cannot be served another rally's
   classification.

2. **Re-export** the website JSON from whatever snapshot is now on disk
   (:mod:`wrc_predictions.export` + :mod:`wrc_predictions.forward_eval`).

Because step 1 is fully guarded, running this offline simply re-exports the
committed snapshot — the deterministic, reproducible path CI and local dev use.

Run:  PYTHONPATH=src python -m wrc_predictions.refresh [--season 2026]
          [--no-fetch] [--skip-forward-eval] [--allow-regression]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config, export, forward_eval

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
        from .build_snapshot import _persons_for_season, assign_codes, build_season
        from .sources.redbull_source import WrcApi

        api = WrcApi()
        # Build the global driver registry over the same season range the committed
        # snapshots used, so codes stay stable across seasons/artifacts.
        years = sorted(set(config.HISTORY_SEASONS) | {season})
        people: dict[str, dict] = {}
        for y in years:
            people.update(_persons_for_season(api, y))
        codes = assign_codes(people)

        snap = build_season(api, season, lambda pid: codes.get(str(pid)))
    except Exception as exc:  # offline / network / API change -> keep committed snapshot
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
    out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"refresh: wrote {out_path} — {fresh}/{snap.get('totalRounds')} rounds, "
          f"{len(snap.get('drivers', []))} drivers.")
    return True


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

    # config.SEASON / COMPLETED_ROUNDS were resolved at import from the on-disk
    # snapshot; a fetch that ADDED rounds is picked up on the next process. The
    # export/forward_eval steps run as SEPARATE processes in the cron so the
    # module-level config re-resolves — here they reflect what was loaded at import.
    path = export.write(export.DEFAULT_OUT)
    print(f"refresh: exported {path}")

    if not args.skip_forward_eval:
        n = forward_eval.write(export.DEFAULT_OUT, config.SEASON)
        print(f"refresh: forward-eval scored {n} round(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
