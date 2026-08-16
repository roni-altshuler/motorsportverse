#!/usr/bin/env python
"""Publish ``evidence.json`` for every project that has scored a round.

The model-vs-baseline comparison is computed ONCE, here, by
:func:`motorsport_core.evidence.build_evidence`, and every site renders the
result through the shared ``EvidencePanel``. Deriving it in TypeScript instead
would put the comparison in eleven independent codebases that drift
independently — and a page that recomputes a number is a second model nobody
benchmarked.

Pairing matters: the block compares model and baseline on the rounds they BOTH
scored, never two independently-averaged means over different round sets. Round
1 has no previous race, so it contributes to neither.

    python scripts/build_evidence.py                 # every project
    python scripts/build_evidence.py f3-predictions  # one project
    python scripts/build_evidence.py --check         # exit 1 if any is stale

Run it after ``forward_eval`` and before the commit step, so the artifact ships
with the round it summarises rather than a round behind.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages/motorsport-core/src"))

from motorsport_core import evidence as core_evidence  # noqa: E402


def _sport_for(project_dir: Path) -> str:
    """The series label the block is stamped with.

    Prefers the registry entry so the label matches what the hub shows; falls
    back to the directory name rather than failing, because a missing catalog
    entry should not stop a project publishing its own evidence.
    """
    reg = ROOT / "registry/projects" / f"{project_dir.name}.json"
    if reg.exists():
        try:
            payload = json.loads(reg.read_text())
            for key in ("shortName", "series", "name", "slug"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except (json.JSONDecodeError, OSError):
            pass
    return project_dir.name.replace("-predictions", "")


def build_for(project_dir: Path) -> tuple[Path, str] | None:
    data_dir = project_dir / "website/public/data"
    forward_eval = data_dir / "forward_eval"
    if not forward_eval.is_dir():
        return None
    block = core_evidence.build_evidence(
        forward_eval,
        calibration_summary=data_dir / "calibration_summary.json",
        promotion_status=data_dir / "promotion_status.json",
        sport=_sport_for(project_dir),
    )
    out = core_evidence.write_evidence(block, data_dir / "evidence.json")
    if block.available:
        headline = block.headline or {}
        verdict = headline.get("verdict", "no headline comparison")
        label = headline.get("baselineLabel") or headline.get("baseline") or "?"
        summary = f"{block.rounds_scored} round(s) — {verdict} vs {label}"
    else:
        summary = block.reason or "no benchmark available"
    return out, summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", help="project directory names (default: all)")
    ap.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any published evidence.json differs from a fresh build",
    )
    args = ap.parse_args()

    candidates = sorted(p for p in (ROOT / "projects").iterdir() if p.is_dir())
    if args.projects:
        wanted = set(args.projects)
        candidates = [p for p in candidates if p.name in wanted]
        unknown = wanted - {p.name for p in candidates}
        if unknown:
            print(f"unknown project(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2

    stale: list[str] = []
    built = 0
    for project in candidates:
        data_dir = project / "website/public/data"
        published = data_dir / "evidence.json"
        before = published.read_text() if published.exists() else None
        result = build_for(project)
        if result is None:
            continue
        out, summary = result
        built += 1
        after = out.read_text()
        if args.check:
            if before is None:
                stale.append(f"{project.name} — no evidence.json is published")
            elif _differs(before, after):
                stale.append(f"{project.name} — published evidence.json is out of date")
            if before is None:
                out.unlink(missing_ok=True)
            else:
                out.write_text(before)
        print(f"{project.name:<28} {summary}")

    if args.check:
        if stale:
            print("\n" + "\n".join(f"STALE: {s}" for s in stale), file=sys.stderr)
            print("Run: python scripts/build_evidence.py", file=sys.stderr)
            return 1
        print(f"\n{built} evidence artifact(s) up to date ✓")
    else:
        print(f"\n{built} evidence artifact(s) written")
    return 0


def _differs(before: str, after: str) -> bool:
    """Compare ignoring generatedAt, which changes on every run by design."""
    try:
        a, b = json.loads(before), json.loads(after)
    except json.JSONDecodeError:
        return True
    for payload in (a, b):
        if isinstance(payload, dict):
            payload.pop("generatedAt", None)
    return a != b


if __name__ == "__main__":
    raise SystemExit(main())
