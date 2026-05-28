"""CI-gatable production-invariant check.

Runs every Phase 10 / Phase 11 production invariant and exits 0 if all
pass, non-zero if any fail. Intended to be wired into CI as a
pre-merge gate.

Usage::

    python deployment_check.py            # full check
    python deployment_check.py --quiet    # silent except on failure
    python deployment_check.py --skip-backfill  # skip the round-trip DB test

The check delegates to the same invariants codified in
``tests/test_deployment_readiness.py`` so the gate cannot drift from
the test suite — there is one source of truth.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_pytest(quiet: bool, skip_backfill: bool) -> int:
    args = [
        sys.executable, "-m", "pytest",
        "tests/test_deployment_readiness.py",
        "tests/test_production_model.py",
        "tests/test_weekend_features.py",
        "--tb=short",
    ]
    if quiet:
        args += ["-q"]
    else:
        args += ["-v"]
    if skip_backfill:
        args += ["--deselect", "tests/test_deployment_readiness.py::test_backfill_idempotency_via_upsert"]
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--quiet", action="store_true",
        help="suppress per-test pass output; only show failures",
    )
    parser.add_argument(
        "--skip-backfill", action="store_true",
        help="skip the backfill idempotency round-trip (faster; useful if "
             "DuckDB write permission is unavailable in CI)",
    )
    args = parser.parse_args(argv)

    rc = run_pytest(args.quiet, args.skip_backfill)
    if rc != 0:
        print()
        print("=" * 60)
        print("DEPLOYMENT CHECK FAILED")
        print("=" * 60)
        print("One or more production invariants have drifted.")
        print("Triage the failures above before merging to main.")
        print("See docs/ARCHITECTURE_AUDIT.md section 11 for the freeze")
        print("contract.")
        return rc

    print()
    print("=" * 60)
    print("DEPLOYMENT CHECK PASSED")
    print("=" * 60)
    print("Production model:    regime_routed_with_weekend_static")
    print("Feature flag env:    F1_PRODUCTION_MODEL_ENABLED  (defaults: 0)")
    print("Canonical feature set: 7 columns (Phase 7 static)")
    print("Archived columns:    3 (Phase 8 dynamic, research-only)")
    print()
    print("Safe to merge to main.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
