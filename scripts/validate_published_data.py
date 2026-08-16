#!/usr/bin/env python3
"""Integrity check over every project's published site data. Exits non-zero on failure.

    python scripts/validate_published_data.py                      # every project
    python scripts/validate_published_data.py f3 nascar            # named projects
    python scripts/validate_published_data.py --json report.json   # machine-readable
    python scripts/validate_published_data.py --allow probability_mass
    python scripts/validate_published_data.py --warn-only          # report, never fail

**Run this after any change to an export.** A schema test proves each file is
well-formed; this asks whether the *corpus* is right — contiguous rounds, dates
that increase, probabilities that add up to the field they describe, a baseline
beside every scored metric, and a calibration gate that is only open on real
results. Every check is documented in ``motorsport_core.integrity``.

A project with nothing published yet is **skipped, not failed**: a scaffolded
series has no forward-eval, and that is its maturity level rather than a defect.

``--allow <check>`` downgrades one named check to a warning. It exists so that a
**known, documented** defect can be carried without disabling the whole gate,
and it is deliberately a command-line flag rather than a config file: the
allowance then appears in the workflow that grants it, where a reader trips over
it, instead of in a settings file nobody opens. Every allowance is still printed
and still counted. See ``docs/KNOWN_ISSUES.md`` for what is currently allowed
and why.

The script deliberately reads only committed JSON. It touches no network, imports
no project package, and needs nothing installed beyond ``motorsport-core`` — so
it runs in CI before any project is installed, and locally in under a second.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Importable without installing the package, so this can run as the first CI
# step and from a bare checkout.
sys.path.insert(0, str(REPO_ROOT / "packages" / "motorsport-core" / "src"))

from motorsport_core import integrity  # noqa: E402


def discover_projects(names: list[str] | None) -> list[tuple[str, Path]]:
    """``(project name, published data dir)`` for every project, or the named ones."""
    projects: list[tuple[str, Path]] = []
    for project_dir in sorted((REPO_ROOT / "projects").iterdir()):
        if not project_dir.is_dir():
            continue
        if names and not any(n in project_dir.name for n in names):
            continue
        projects.append((project_dir.name, project_dir / "website" / "public" / "data"))
    return projects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "projects",
        nargs="*",
        help="substrings of project directory names; default is every project",
    )
    parser.add_argument("--json", type=Path, help="write a machine-readable report here")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="CHECK",
        help=(
            "downgrade this check to a warning (repeatable). For KNOWN, DOCUMENTED "
            "debt only — see docs/KNOWN_ISSUES.md"
        ),
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="print findings but always exit 0 (for a first pass on a new series)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print passing checks too, not only failures",
    )
    args = parser.parse_args(argv)

    reports = [
        integrity.check_published_data(data_dir, project=name, root=REPO_ROOT)
        for name, data_dir in discover_projects(args.projects or None)
    ]
    if not reports:
        print("no projects matched", file=sys.stderr)
        return 2

    allowed = set(args.allow)
    total_checks = sum(len(r.findings) for r in reports)
    all_failures = [f for r in reports for f in r.failures]
    blocking = [f for f in all_failures if f.check not in allowed]
    waived = [f for f in all_failures if f.check in allowed]

    for report in reports:
        if not report.findings:
            print(f"{report.project:28} — nothing published yet (skipped)")
            continue
        hard = [f for f in report.failures if f.check not in allowed]
        soft = [f for f in report.failures if f.check in allowed]
        if hard:
            status = f"{len(hard)} FAILURE(S)"
        elif soft:
            status = f"OK ({len(soft)} allowed)"
        else:
            status = "OK"
        print(f"{report.project:28} {len(report.findings):3} checks  {status}")
        for finding in report.findings:
            if finding.ok and not args.verbose:
                continue
            prefix = "ALLOWED" if (not finding.ok and finding.check in allowed) else ""
            print(f"    {prefix}{'  ' if prefix else ''}{finding}")

    print(
        f"\n{total_checks} checks over {len(reports)} project(s); "
        f"{len(blocking)} failure(s)"
        + (f", {len(waived)} allowed by --allow {sorted(allowed)}" if waived else "")
    )
    if waived:
        print(
            "Allowed findings are DEBT, not passes. They are documented in "
            "docs/KNOWN_ISSUES.md and the allowance is removed when the fix lands."
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps([r.to_json() for r in reports], indent=2) + "\n", encoding="utf-8"
        )
        print(f"report written to {args.json}")

    if blocking and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
