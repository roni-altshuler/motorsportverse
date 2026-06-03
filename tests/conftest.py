"""Shared pytest fixtures and project-root path setup."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DATA = PROJECT_ROOT / "website" / "public" / "data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True, scope="session")
def _protect_committed_registry_metadata():
    """Defense-in-depth: the model registry defaults to the real
    ``models/registry/`` tree, so a test that runs the production export path
    without disabling the registry will rewrite a committed ``metadata.json``.

    Tests must isolate the registry (``ModelRegistry(root=tmp_path)`` or
    ``F1_REGISTRY_ENABLED=0``). This fixture snapshots every committed
    ``metadata.json`` and restores any that a test dirtied, FAILING the session
    so the offending test is fixed rather than silently polluting the tree.
    """
    registry_dir = PROJECT_ROOT / "models" / "registry"
    snapshot = {p: p.read_bytes() for p in registry_dir.rglob("metadata.json")}
    yield
    dirtied = [p for p, original in snapshot.items()
               if p.exists() and p.read_bytes() != original]
    for p in dirtied:
        p.write_bytes(snapshot[p])
    if dirtied:
        names = ", ".join(str(p.relative_to(PROJECT_ROOT)) for p in dirtied)
        pytest.fail(
            "A test mutated committed registry metadata (restored): "
            f"{names}. Isolate the registry with ModelRegistry(root=tmp_path) "
            "or monkeypatch.setenv('F1_REGISTRY_ENABLED', '0').",
            pytrace=False,
        )
