#!/usr/bin/env python3
"""
rebuild_replay_geometry.py
==========================
Overwrite the ``geometry.path`` of the committed Race Theatre replays
(``website/public/data/replays/round_NN.json``) with a smooth, high-fidelity
outline reconstructed from each replay's own baked car positions
(:func:`replay_geometry.high_fidelity_path`).

Offline, deterministic, idempotent — re-running rewrites byte-identical files.
Only ``geometry.path`` changes; every other key (corners, viewBox, metresPerUnit,
cars, stints, finish, …) is preserved, and the compact JSON envelope matches
``export_race_replay._write`` / ``slim_replays`` exactly (no schema drift).

Usage:
    python src/rebuild_replay_geometry.py                # all rounds
    python src/rebuild_replay_geometry.py --round 6      # one round
    python src/rebuild_replay_geometry.py --dry-run      # report, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_geometry import apply_high_fidelity_geometry, high_fidelity_path  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPLAYS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "replays"


def _serialize(payload: dict[str, Any]) -> str:
    """Compact JSON + trailing newline — identical envelope to the baker/slimmer."""
    return json.dumps(payload, separators=(",", ":")) + "\n"


def _path_points(path: str) -> int:
    return max(0, path.count("L") + path.count("M"))


def rebuild_file(path: Path, *, dry_run: bool = False) -> tuple[bool, str]:
    payload = json.loads(path.read_text())
    geo = payload.get("geometry")
    if not isinstance(geo, dict):
        return False, "no geometry block"
    before = geo.get("path", "")
    n_corners_before = len(geo.get("corners") or [])
    if high_fidelity_path(payload) is None:
        return False, "reconstruction unavailable — kept existing path"
    changed = apply_high_fidelity_geometry(payload)
    if not changed:
        return False, f"unchanged ({_path_points(before)} pts)"
    n_corners_after = len(geo.get("corners") or [])
    msg = f"{_path_points(before)} → {_path_points(geo['path'])} pts"
    if n_corners_after < n_corners_before:
        msg += f"; dropped {n_corners_before} off-track corners (prior-year frame)"
    if not dry_run:
        path.write_text(_serialize(payload))
    return True, msg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", type=int, default=None, help="Only this round")
    ap.add_argument("--dry-run", action="store_true", help="Report, write nothing")
    args = ap.parse_args(argv)

    if not REPLAYS_DIR.exists():
        print(f"no replays dir: {REPLAYS_DIR}", file=sys.stderr)
        return 1

    if args.round is not None:
        files = [REPLAYS_DIR / f"round_{args.round:02d}.json"]
    else:
        files = sorted(REPLAYS_DIR.glob("round_*.json"))

    changed = 0
    for f in files:
        if not f.exists():
            print(f"  {f.name}: missing")
            continue
        did, msg = rebuild_file(f, dry_run=args.dry_run)
        changed += int(did)
        flag = "✓" if did else "·"
        print(f"  {flag} {f.name}: {msg}")
    verb = "would rewrite" if args.dry_run else "rewrote"
    print(f"{verb} {changed}/{len(files)} replays")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
