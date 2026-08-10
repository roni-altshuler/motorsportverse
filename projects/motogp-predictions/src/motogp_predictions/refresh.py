"""Refresh the committed MotoGP snapshot, then re-export the website data.

Two steps, in order:

1. **Re-pull** (network) the current season from the official results API via the
   committed ingester (:mod:`motogp_predictions.build_snapshot`), guarded so that
   offline / CI is a **graceful no-op**: any failure (no network, API down, import
   error) leaves the committed ``data/official_<season>.json`` untouched. A refresh
   can only ever *add* completed rounds — it refuses to overwrite a healthy snapshot
   with one that has FEWER completed rounds (the freshness/regression guard that
   protects every series against a transient empty scrape wiping real data). Rider
   codes are assigned over the same season range the committed snapshots used, so a
   rider keeps a stable code (the wrong-event guard is inherent: the API keys every
   round by event UUID, so a round can't be served another event's classification).

2. **Re-export** the website JSON from whatever snapshot is now on disk
   (:mod:`motogp_predictions.export` + :mod:`motogp_predictions.forward_eval`).

Because step 1 is fully guarded, running this offline simply re-exports the
committed snapshot — the deterministic, reproducible path CI and local dev use.

Run:  PYTHONPATH=src python -m motogp_predictions.refresh [--season 2026]
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
        from .build_snapshot import assign_rider_codes, build_season
        from .sources.pulselive_source import MotoGPApi

        api = MotoGPApi()
        # Build the global rider registry over the same season range the committed
        # snapshots used, so codes stay stable across seasons/artifacts.
        years = sorted(set(config.HISTORY_SEASONS) | {season})
        riders: dict[str, dict] = {}
        for y in years:
            su = api.season_uuid(y)
            cat = api.premier_category_uuid(su) if su else None
            if not (su and cat):
                continue
            for ev in api.events(su, finished_only=True):
                for s in api.sessions(ev["id"], cat):
                    if s.get("type") in ("RAC", "SPR"):
                        for r in api.classification(s["id"]):
                            rd = r.get("rider") or {}
                            if rd.get("id"):
                                riders.setdefault(rd["id"], {"full_name": rd.get("full_name")})
        codes = assign_rider_codes(riders)

        snap = build_season(api, season, lambda rid: codes.get(rid))
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
    out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"refresh: wrote {out_path} — {fresh}/{snap.get('totalRounds')} rounds, "
          f"{len(snap.get('riders', []))} riders.")
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
    # export below reflects whatever the module-level config resolved to.
    path = export.write(export.DEFAULT_OUT)
    print(f"refresh: exported {path}")

    if not args.skip_forward_eval:
        n = forward_eval.write(export.DEFAULT_OUT, config.SEASON)
        print(f"refresh: forward-eval scored {n} round(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
