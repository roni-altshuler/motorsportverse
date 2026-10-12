"""Provenance-pinned historical inputs for temporal publication tests."""
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPAIR_SNAPSHOT = Path(__file__).parent / "fixtures/publication-repair-2026-10-11"


def repair_input(relative):
    """Return exact saved bytes, never a modified copy of current public data."""
    manifest = json.loads((REPAIR_SNAPSHOT / "source-manifest.json").read_text())
    source = REPAIR_SNAPSHOT / relative
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["files"][relative]["sha256"]
    return source


def result_available_input():
    """The separately saved held forecast after a legitimate result arrived."""
    fixtures = PROJECT_ROOT / "website/src/__tests__/fixtures/publication-hold"
    manifest = json.loads((fixtures / "source-manifest.json").read_text())
    source = fixtures / "singapore-result-available.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["files"][source.name]["sha256"]
    return source
