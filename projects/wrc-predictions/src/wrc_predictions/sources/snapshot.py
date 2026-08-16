"""Committed-snapshot reader for FIA World Rally Championship.

The convention every implemented series in this repo follows: a committed
snapshot under ``data/official_<season>.json`` is the offline source of truth,
so a build never depends on the network and a flaky live source no-ops the run
rather than publishing a degraded one.

**No snapshot exists for WRC yet.** This module therefore reports
emptiness. It does not synthesise a plausible calendar, a plausible entry list
or a plausible result — sparse coverage stays genuinely missing (``docs/EVIDENCE.md``
rule 6), and a scaffold that returns convincing fake data is far more dangerous
than one that returns nothing, because the fake data reaches a chart.
"""
from __future__ import annotations

import json

from .. import config


class SnapshotUnavailable(RuntimeError):
    """Raised when a caller demands data that has not been ingested."""


def load(season: int) -> dict | None:
    """The season snapshot, or ``None`` when nothing has been ingested.

    ``None`` and ``{}`` mean different things and both are preserved: the
    first is "never ingested", the second is "ingested and genuinely empty".
    """
    path = config.snapshot_path(season)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable(f"{path} exists but is unreadable: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def require(season: int) -> dict:
    """The snapshot, or a loud failure naming exactly what is missing."""
    payload = load(season)
    if payload is None:
        raise SnapshotUnavailable(
            f"no {config.SHORT_NAME} snapshot for {season}. Expected "
            f"{config.snapshot_path(season)}, which would be produced by an "
            f"ingester reading {config.SOURCE_NAME} ({config.SOURCE_URL}). "
            f"See the project README for what has to be decided before that "
            f"ingester can be written."
        )
    return payload


def available_seasons() -> list[int]:
    """Seasons with a committed snapshot. Empty until one is ingested."""
    if not config.DATA_DIR.is_dir():
        return []
    seasons: list[int] = []
    for path in sorted(config.DATA_DIR.glob("official_*.json")):
        stem = path.stem.removeprefix("official_")
        if stem.isdigit():
            seasons.append(int(stem))
    return seasons


__all__ = ["SnapshotUnavailable", "load", "require", "available_seasons"]
