#!/usr/bin/env python3
"""
slim_replays.py
===============
Post-process the committed Race Theatre replays
(``website/public/data/replays/round_NN.json``) to shrink the payload the
browser downloads **without changing what it animates**.

The replays are already baked compact (no pretty-print whitespace) and their
per-frame car coordinates are already rounded to 1 decimal by
``export_race_replay.py``. The remaining safe wins are purely representational:

  * **Integral floats lose their trailing ``.0``.** ``0.0`` → ``0``,
    ``748.0`` → ``748``. JSON and JavaScript treat these as the same number, and
    the leader's gap array (``0.0`` every frame) plus every whole-unit coordinate
    account for a large share of the bytes.
  * **A few over-precise scalars are capped** to a display-sensible precision
    (``metresPerUnit`` and the final-classification ``gap`` were baked at 3-4 dp;
    2 dp is well below anything the UI shows).

Precision policy (see the ``*_DECIMALS`` constants) is the single source of truth
and is shared with :mod:`export_race_replay` (imported there via
:func:`slim_payload`) so freshly baked replays are born slim too. The transform is
**idempotent** — re-running it on an already-slim file rewrites identical bytes —
and never changes the schema: keys, array lengths, frame counts and ordering are
untouched; only numeric representation and (already-absent) whitespace shrink.

Usage:
    python src/slim_replays.py                 # slim every round_NN.json in place
    python src/slim_replays.py --dry-run       # report savings, write nothing
    python src/slim_replays.py --round 9       # a single round
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPLAYS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "replays"

# On-screen coordinate frame is the 0..1000 viewBox, so 0.1 unit is sub-pixel:
# 1 dp is the visual floor for car x/y. Gaps/laps only ever surface as coarse
# timing text, so a couple of decimals is plenty.
COORD_DECIMALS = 1        # car x/y, circuit corner x/y
GAP_DECIMALS = 2          # per-frame gap-to-leader seconds
FINISH_GAP_DECIMALS = 2   # final-classification gap seconds
POINTS_DECIMALS = 1       # championship points (integers in practice)
TIME_DECIMALS = 1         # trackStatus segment start time
METRES_DECIMALS = 2       # geometry.metresPerUnit scale factor


def _num(value: Any, decimals: int) -> Any:
    """Round a float to ``decimals`` and drop a redundant ``.0`` by returning an
    ``int`` when the rounded value is integral. ``None``, ``bool`` and ``int``
    pass through untouched; non-finite floats (never valid in JSON) fold to
    ``None`` so the output stays parseable."""
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        rounded = round(value, decimals)
        as_int = round(rounded)
        return as_int if rounded == as_int else rounded
    return value


def slim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce numeric precision across a replay dict **in place** and return it.

    Only touches the numeric leaves listed in the precision policy; every key,
    array length and ordering is preserved, so the schema is unchanged.
    """
    geo = payload.get("geometry")
    if isinstance(geo, dict):
        if geo.get("metresPerUnit") is not None:
            geo["metresPerUnit"] = _num(geo["metresPerUnit"], METRES_DECIMALS)
        for corner in geo.get("corners") or []:
            if isinstance(corner, dict):
                for k in ("x", "y"):
                    if k in corner:
                        corner[k] = _num(corner[k], COORD_DECIMALS)

    cars = payload.get("cars")
    if isinstance(cars, dict):
        for car in cars.values():
            if not isinstance(car, dict):
                continue
            for k in ("x", "y"):
                if isinstance(car.get(k), list):
                    car[k] = [_num(v, COORD_DECIMALS) for v in car[k]]
            if isinstance(car.get("gap"), list):
                car["gap"] = [_num(v, GAP_DECIMALS) for v in car["gap"]]
            # `lap` is already an int array — left as-is.

    for status in payload.get("trackStatus") or []:
        if isinstance(status, dict) and "t" in status:
            status["t"] = _num(status["t"], TIME_DECIMALS)

    for entry in payload.get("finish") or []:
        if isinstance(entry, dict):
            if "gap" in entry:
                entry["gap"] = _num(entry["gap"], FINISH_GAP_DECIMALS)
            if "points" in entry:
                entry["points"] = _num(entry["points"], POINTS_DECIMALS)

    return payload


def _serialize(payload: dict[str, Any]) -> str:
    """Compact JSON (no whitespace) + one trailing newline — byte-for-byte the
    same envelope ``export_race_replay._write`` produces."""
    return json.dumps(payload, separators=(",", ":")) + "\n"


def slim_file(path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """Slim one replay file in place. Returns (bytes_before, bytes_after)."""
    before = path.stat().st_size
    payload = json.loads(path.read_text())
    slim_payload(payload)
    text = _serialize(payload)
    after = len(text.encode("utf-8"))
    if not dry_run and after != before:
        path.write_text(text)
    elif not dry_run:
        # Rewrite anyway to normalise (e.g. already-optimal but different bytes);
        # cheap and keeps the on-disk form canonical.
        path.write_text(text)
    return before, after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", type=int, default=None, help="Slim a single round")
    parser.add_argument("--dry-run", action="store_true", help="Report savings, write nothing")
    args = parser.parse_args(argv)

    if not REPLAYS_DIR.exists():
        print(f"no replays dir at {REPLAYS_DIR}")
        return 0

    if args.round is not None:
        files = [REPLAYS_DIR / f"round_{args.round:02d}.json"]
    else:
        files = sorted(REPLAYS_DIR.glob("round_*.json"))
    files = [f for f in files if f.exists()]
    if not files:
        print("no replay files matched")
        return 0

    total_before = total_after = 0
    for path in files:
        before, after = slim_file(path, dry_run=args.dry_run)
        total_before += before
        total_after += after
        pct = 100 * (before - after) / before if before else 0.0
        print(f"  {path.name}: {before/1024:8.1f} KB → {after/1024:8.1f} KB  (-{pct:4.1f}%)")

    saved = total_before - total_after
    pct = 100 * saved / total_before if total_before else 0.0
    tag = " (dry-run, nothing written)" if args.dry_run else ""
    print(
        f"TOTAL: {total_before/1_048_576:.2f} MB → {total_after/1_048_576:.2f} MB  "
        f"(-{saved/1_048_576:.2f} MB, -{pct:.1f}%){tag}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
