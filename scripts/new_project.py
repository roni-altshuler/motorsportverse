#!/usr/bin/env python3
"""Scaffold a new MotorsportVerse project from templates/project-template/.

Usage:
    python scripts/new_project.py <slug> --sport "Sport Name" \
        --summary "One-line blurb" [--category open-wheel] [--accent "#RRGGBB"]

Creates ``projects/<slug>/`` from the template (substituting placeholders) and a
registry entry ``registry/projects/<slug>.json`` at maturity ``concept``. Run
``scripts/build_registry.py`` afterwards to validate + rebuild the index.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "project-template"
PROJECTS = ROOT / "projects"
REGISTRY = ROOT / "registry" / "projects"

CATEGORIES = ["open-wheel", "stock", "endurance", "rally", "motorcycle", "electric"]


def _pkg_name(slug: str) -> str:
    return slug.replace("-", "_")


def _substitute(text: str, mapping: dict[str, str]) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


def scaffold(args: argparse.Namespace) -> int:
    slug = args.slug
    dest = PROJECTS / slug
    if dest.exists():
        print(f"ERROR: {dest} already exists", flush=True)
        return 1

    pkg = _pkg_name(slug)
    mapping = {
        "__SLUG__": slug,
        "__SLUG_PKG__": pkg,
        "__NAME__": args.name or slug.replace("-", " ").title(),
        "__SPORT__": args.sport,
        "__SUMMARY__": args.summary,
    }

    # Copy template tree, renaming the package dir and substituting placeholders.
    for src in TEMPLATE.rglob("*"):
        rel = src.relative_to(TEMPLATE)
        rel_str = _substitute(str(rel), mapping)
        target = dest / rel_str
        if src.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_substitute(src.read_text(), mapping))

    # Registry entry (concept).
    entry = {
        "slug": slug,
        "name": mapping["__NAME__"],
        "sport": args.sport,
        "category": args.category,
        "maturity": "concept",
        "summary": args.summary,
        "description": "",
        "repo": "",
        "website": "",
        "docs": "https://motorsportverse.org/docs",
        "datasets": [],
        "models": [],
        "tags": ["concept"],
        "icon": f"/brand/sports/{slug.split('-')[0]}.svg",
        "accent": args.accent,
        "uses_core": ["calibration", "eval"],
        "maintainers": [],
        "added": args.added,
    }
    (REGISTRY / f"{slug}.json").write_text(json.dumps(entry, indent=2) + "\n")

    print(f"Created projects/{slug}/ and registry/projects/{slug}.json")
    print("Next: python scripts/build_registry.py")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("slug", help="kebab-case slug, e.g. 'nascar-predictions'")
    p.add_argument("--sport", required=True, help="Display sport name, e.g. 'NASCAR'")
    p.add_argument("--summary", required=True, help="One-line catalog blurb")
    p.add_argument("--name", default=None, help="Display name (defaults from slug)")
    p.add_argument("--category", default="open-wheel", choices=CATEGORIES)
    p.add_argument("--accent", default="#38e1c6", help="Hex accent color")
    p.add_argument("--added", default="", help="ISO date registered (pass today's date)")
    if not TEMPLATE.exists():
        print(f"ERROR: template missing at {TEMPLATE}", flush=True)
        return 1
    return scaffold(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
