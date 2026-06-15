#!/usr/bin/env python3
"""Validate every registry/projects/*.json against the schema and build index.json.

The project catalog under ``registry/projects/`` is the source of truth for the
ecosystem website's project directory. This script:

  1. validates each entry against ``registry/schema/project.schema.json``,
  2. checks slug uniqueness and that slug == filename stem,
  3. emits an aggregate ``registry/index.json`` (sorted, with maturity counts),
  4. copies it to ``website/public/data/registry.json`` for the static build.

Exits non-zero on any invalid entry so CI gates a broken catalog.

Uses ``jsonschema`` if installed; otherwise falls back to a built-in minimal
validator covering required fields + enums (keeps the script dependency-free).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "registry" / "projects"
SCHEMA_PATH = ROOT / "registry" / "schema" / "project.schema.json"
INDEX_PATH = ROOT / "registry" / "index.json"
WEBSITE_COPY = ROOT / "website" / "public" / "data" / "registry.json"

MATURITY_ORDER = ["production", "experimental", "in-development", "concept", "archived"]


def _load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def _validate(entry: dict, schema: dict, source: str) -> list[str]:
    """Return a list of validation errors (empty == valid)."""
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft7Validator(schema)
        return [f"{source}: {e.message}" for e in validator.iter_errors(entry)]
    except ImportError:
        pass

    # Minimal fallback validator.
    errors: list[str] = []
    for field in schema.get("required", []):
        if field not in entry:
            errors.append(f"{source}: missing required field '{field}'")
    props = schema.get("properties", {})
    for key, spec in props.items():
        if key in entry and "enum" in spec and entry[key] not in spec["enum"]:
            errors.append(f"{source}: '{key}'={entry[key]!r} not in {spec['enum']}")
    if schema.get("additionalProperties") is False:
        for key in entry:
            if key not in props:
                errors.append(f"{source}: unknown field '{key}'")
    return errors


def main() -> int:
    schema = _load_json(SCHEMA_PATH)
    files = sorted(PROJECTS_DIR.glob("*.json"))
    if not files:
        print("ERROR: no project entries found", file=sys.stderr)
        return 1

    errors: list[str] = []
    entries: list[dict] = []
    seen_slugs: set[str] = set()

    for path in files:
        entry = _load_json(path)
        errors.extend(_validate(entry, schema, path.name))
        slug = entry.get("slug")
        if slug != path.stem:
            errors.append(f"{path.name}: slug '{slug}' != filename stem '{path.stem}'")
        if slug in seen_slugs:
            errors.append(f"{path.name}: duplicate slug '{slug}'")
        seen_slugs.add(slug)
        entries.append(entry)

    if errors:
        print("Registry validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Sort: maturity rank, then name.
    rank = {m: i for i, m in enumerate(MATURITY_ORDER)}
    entries.sort(key=lambda e: (rank.get(e["maturity"], 99), e["name"]))

    counts: dict[str, int] = {}
    for e in entries:
        counts[e["maturity"]] = counts.get(e["maturity"], 0) + 1

    index = {
        "generated_by": "scripts/build_registry.py",
        "count": len(entries),
        "maturity_counts": counts,
        "projects": entries,
    }

    INDEX_PATH.write_text(json.dumps(index, indent=2) + "\n")
    WEBSITE_COPY.parent.mkdir(parents=True, exist_ok=True)
    WEBSITE_COPY.write_text(json.dumps(index, indent=2) + "\n")

    print(f"OK: {len(entries)} projects validated.")
    print(f"  maturity: {counts}")
    print(f"  wrote {INDEX_PATH.relative_to(ROOT)}")
    print(f"  wrote {WEBSITE_COPY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
