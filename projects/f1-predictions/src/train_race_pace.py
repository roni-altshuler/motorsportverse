"""Offline trainer for the per-lap race-pace ensemble.

Why this exists
---------------
The per-lap race-pace model in ``models/race_pace.py`` (A-P1.1 Step 1) is
trained once on multi-season FastF1 race telemetry and then reused by the
race simulator (Step 2) lap-by-lap for every weekend.  We don't want to
retrain it inside ``update_predictions.yml`` (FastF1 rate-limits at 500
req/h; full multi-season fetch + training is ~15-30 minutes).

This CLI is the training entrypoint.  Run it once locally — or in a
scheduled CI job (kept separate from the weekend cron) — to populate the
registry.  The integration helper in ``models/race_simulator_runner.py``
then picks up whichever race-pace model is latest in the registry.

Usage
-----
::

    # Train on 2023-2025 races, save to the registry
    python train_race_pace.py --seasons 2023,2024,2025

    # Restrict to a few rounds (useful when iterating)
    python train_race_pace.py --seasons 2024 --rounds 1-6

    # Custom registry root (e.g. testing)
    python train_race_pace.py --seasons 2024 --rounds 1 --registry-root /tmp/registry

Registry key
------------
The trained ensemble is saved under ``(meta_season, meta_round)`` where:
  - ``meta_season`` is the largest season in the training set
  - ``meta_round`` is 99 (a sentinel meaning "trained on multi-season data,
    not weekend-of-N", chosen because it's outside the 1..30 valid range
    a normal weekend would use)

This lets ``ModelRegistry.list_all()`` still find the artefacts via
``metadata["kind"] == "race-pace"`` filtering.

Constraints
-----------
* Pure-additive.  Does not modify f1_prediction_utils.py, leakage.py,
  forward_eval.py, or any exporter.
* FastF1 cache reuse — the existing ``f1_cache/`` directory holds session
  data between runs so re-training only re-trains on already-fetched data.
* Cooperative with the rate-limit — sequential per-(season, round); the
  caller can split the run across multiple invocations by passing
  different ``--rounds`` slices.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from models.race_pace import build_training_dataset, train_race_pace_model
from models.registry import ModelRegistry

# Sentinel round number for the multi-season race-pace artefact in the
# registry.  Chosen above the 1..30 valid range a real weekend would use,
# so it can't collide with a per-weekend registration.  Stored explicitly
# in the metadata so consumers don't have to remember the number.
RACE_PACE_REGISTRY_ROUND: int = 99
RACE_PACE_METADATA_KIND: str = "race-pace"


def _parse_seasons(spec: str) -> list[int]:
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(chunk))
    return sorted(out)


def _parse_rounds(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif chunk:
            out.add(int(chunk))
    return sorted(out)


def _registered_race_pace(registry: ModelRegistry) -> tuple[int, int, dict] | None:
    """Return ``(season, round, metadata)`` for the newest registered race-pace
    ensemble whose binary artefacts are present on disk, else ``None``.

    ``metadata.json`` is committed to git, and the cron force-adds the
    ``*.joblib`` binaries alongside it, so a registered sentinel is fully usable
    on a fresh runner.  We require at least one binary (not just metadata) so a
    metadata-only entry never masks a genuinely missing model.
    """
    try:
        entries = registry.list_all()
    except Exception:
        return None
    candidates = [
        (s, r, m) for s, r, m in entries if m.get("kind") == RACE_PACE_METADATA_KIND
    ]
    candidates.sort(key=lambda row: (row[0], row[1]))
    for season, round_num, meta in reversed(candidates):
        round_dir = registry.root / f"{season:04d}_round_{round_num:02d}"
        if round_dir.is_dir() and any(
            p.suffix in (".joblib", ".pt") for p in round_dir.iterdir()
        ):
            return (season, round_num, meta)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train the per-lap race-pace ensemble and save to the "
        "model registry."
    )
    parser.add_argument(
        "--seasons",
        type=str,
        required=True,
        help="Comma- or range-separated seasons, e.g. '2023,2024,2025' or '2024'.",
    )
    parser.add_argument(
        "--rounds",
        type=str,
        default=None,
        help="Optional round filter, e.g. '1-10' or '3,5,7'. Default: 1-22.",
    )
    parser.add_argument(
        "--registry-root",
        type=Path,
        default=None,
        help="Override the model-registry root directory (testing only).",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Hold-out fraction for in-training validation.  Default 0.2.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="RNG seed for the train/test split.  Default 42 per project convention.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-round chatter.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retrain even when a race-pace ensemble is already registered "
        "(the default is to no-op in that case).",
    )
    args = parser.parse_args(argv)

    # ── Skip guard ──────────────────────────────────────────────────────────
    # The race-pace ensemble is fit on IMMUTABLE multi-season history, so once a
    # sentinel entry (round 99) with its binaries is registered there is nothing
    # to recompute.  Re-running unconditionally means re-fetching up to 176
    # historical FastF1 sessions on *every* scheduled poll — which exhausts the
    # 500-req/h FastF1 rate limit and then starves the live pipeline of its
    # budget (observed in the race-weekend cron: this step rate-limited, then
    # load_multi_year_data crashed the whole run with "No data for <GP>").  The
    # committed sentinel binaries are all the simulator needs, so default to a
    # no-op; pass --force to deliberately retrain locally.
    registry_root = (
        args.registry_root
        if args.registry_root is not None
        else ModelRegistry.__dataclass_fields__["root"].default
    )
    if not args.force:
        existing = _registered_race_pace(ModelRegistry(root=registry_root))
        if existing is not None:
            season_e, round_e, _ = existing
            print(
                f"Race-pace ensemble already registered "
                f"({season_e:04d}_round_{round_e:02d}); skipping retrain "
                f"(pass --force to override).",
                file=sys.stderr,
            )
            return 0

    seasons = _parse_seasons(args.seasons)
    rounds = _parse_rounds(args.rounds) or list(range(1, 23))
    pairs = [(s, r) for s in seasons for r in rounds]
    if not pairs:
        print("No (season, round) pairs to train on.", file=sys.stderr)
        return 2

    if not args.quiet:
        print(
            f"Training race-pace ensemble on {len(pairs)} race(s) "
            f"across seasons {seasons[0]}-{seasons[-1]}...",
            file=sys.stderr,
        )

    feature_df, encoders = build_training_dataset(pairs)
    if feature_df.empty:
        print("No lap data loaded.  Check FastF1 cache / network.", file=sys.stderr)
        return 2

    if not args.quiet:
        print(
            f"Loaded {len(feature_df):,} lap rows from "
            f"{len(encoders['circuit'])} distinct circuits.",
            file=sys.stderr,
        )

    artifacts = train_race_pace_model(
        feature_df, test_size=args.test_size, random_state=args.random_state
    )

    if not args.quiet:
        m = artifacts["metrics"]
        print(
            f"Training done. ensemble_mae={m['ensemble_mae_s']:.3f}s  "
            f"(gbr {m['gbr_mae_s']:.3f}s, xgb {m['xgb_mae_s']:.3f}s).  "
            f"n_train={m['n_train']}  n_test={m['n_test']}",
            file=sys.stderr,
        )

    # Persist to the registry under a sentinel round number so it doesn't
    # collide with per-weekend registrations.  Encoders + feature columns +
    # metrics ride along in metadata.json.
    registry = ModelRegistry(root=registry_root)
    target_season = seasons[-1]
    models_dict = {
        "race_pace_gbr": artifacts["gbr"],
        "race_pace_xgb": artifacts["xgb"],
    }
    metadata = {
        "kind": RACE_PACE_METADATA_KIND,
        "feature_columns": artifacts["feature_columns"],
        "ensemble_weights": artifacts["ensemble_weights"],
        "encoders": encoders,
        "metrics": artifacts["metrics"],
        "training_seasons": seasons,
        "training_rounds": rounds,
        "training_pair_count": len(pairs),
        "training_row_count": int(len(feature_df)),
    }
    target_dir = registry.save(
        season=target_season,
        round_num=RACE_PACE_REGISTRY_ROUND,
        models=models_dict,
        metadata=metadata,
    )

    if not args.quiet:
        print(
            f"Saved race-pace ensemble to registry at "
            f"{target_dir.relative_to(Path.cwd()) if target_dir else '<disabled>'}.",
            file=sys.stderr,
        )
        print(
            f"Metadata: {json.dumps({k: v for k, v in metadata.items() if k != 'encoders'}, default=str, indent=2)}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
