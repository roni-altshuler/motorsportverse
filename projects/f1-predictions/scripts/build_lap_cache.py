#!/usr/bin/env python
"""Populate the committed offline lap store (features/data/lap_cache/).

Why this exists
---------------
The race-weekend cron builds per-circuit driver-pace features from the previous
seasons' race laps via FastF1.  Those laps are IMMUTABLE, but the FastF1
live-timing API is routinely unreachable from GitHub Actions runners (empty
responses + the 500-req/h rate limit), which crashed the pipeline in
``load_multi_year_data`` with ``No data for <GP>``.  This script materialises
each needed session to a committed parquet so CI reads them offline and never
touches the network for closed seasons.

Run it locally (where FastF1 works), then commit the generated parquet files::

    PYTHONPATH=src:. python scripts/build_lap_cache.py                 # whole calendar
    PYTHONPATH=src:. python scripts/build_lap_cache.py --circuits Belgium,Hungary
    PYTHONPATH=src:. python scripts/build_lap_cache.py --force         # refetch even if cached

FastF1 rate-limits at ~500 req/h (~7 calls per session → ~70 sessions/run).
Already-cached sessions are skipped, so if you hit the limit just re-run later
to fill the rest — it is fully resumable.
"""
from __future__ import annotations

import argparse
import sys

# The pipeline modules resolve from src/ and the project root.
sys.path.insert(0, "src")
sys.path.insert(0, ".")

from export_website_data import CALENDAR, GP_DATA_YEARS  # noqa: E402
from f1_prediction_utils import (  # noqa: E402
    _lap_cache_path,
    enable_cache,
    load_race_session,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--circuits",
        type=str,
        default=None,
        help="Comma-separated gp_key filter (default: whole calendar).",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="R",
        help="FastF1 session code to cache (default: R).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch and overwrite even when a snapshot already exists.",
    )
    args = parser.parse_args(argv)

    wanted = (
        {c.strip() for c in args.circuits.split(",") if c.strip()}
        if args.circuits
        else None
    )

    enable_cache()

    # Iterate in calendar order so upcoming circuits are cached first.
    seen_keys: set[str] = set()
    targets: list[tuple[str, int]] = []
    for _rnd, info in sorted(CALENDAR.items()):
        gp_key = info["gp_key"]
        if wanted is not None and gp_key not in wanted:
            continue
        for year in GP_DATA_YEARS.get(gp_key, [2023, 2024, 2025]):
            # Dedup on the RESOLVED snapshot path (Madrid → Spain share a file).
            path = _lap_cache_path(year, gp_key, args.session)
            if path in seen_keys:
                continue
            seen_keys.add(path)
            targets.append((gp_key, year))

    ok, skipped, failed = 0, 0, 0
    for gp_key, year in targets:
        path = _lap_cache_path(year, gp_key, args.session)
        if path.exists() and not args.force:
            skipped += 1
            continue
        if args.force and path.exists():
            path.unlink()
        try:
            load_race_session(year, gp_key, args.session)
            ok += 1
        except Exception as exc:  # rate limit / network / missing session
            failed += 1
            print(f"  ⚠️  {year} {gp_key}: {exc}")

    print(
        f"\nLap cache: {ok} fetched, {skipped} already cached, {failed} failed "
        f"→ {LAP_CACHE_SUMMARY()}"
    )
    return 0 if failed == 0 else 1


def LAP_CACHE_SUMMARY() -> str:
    from f1_prediction_utils import LAP_CACHE_DIR

    n = len(list(LAP_CACHE_DIR.glob("*.parquet"))) if LAP_CACHE_DIR.exists() else 0
    return f"{n} snapshot(s) in {LAP_CACHE_DIR}"


if __name__ == "__main__":
    raise SystemExit(main())
