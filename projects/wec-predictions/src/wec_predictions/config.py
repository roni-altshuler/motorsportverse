"""Static configuration for FIA World Endurance Championship.

Facts about the series, and an honest record of what is not yet wired. Nothing
here is a result — this module is deliberately incapable of producing one.

The golden template (``projects/f3-predictions``) resolves the active season via
env → ``data/active_season.json`` marker → literal default, and this follows the
same order so a promoted project does not have to change how it is configured.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

SPORT = "FIA World Endurance Championship"
SHORT_NAME = "WEC"
SLUG = "wec"
ACCENT = "#E8002D"

#: What a single row of the classification is. NOT always a person — see README.
COMPETITOR_UNIT = "car entry"

#: Classes that race simultaneously. A single field-wide order mixes them and is
#: not the quantity anyone wants; every class is scored separately.
CLASSES: tuple[str, ...] = ("HYPERCAR", "LMP2", "LMGT3",)

#: Where results would come from once a source is implemented.
SOURCE_NAME = "the official FIA WEC results pages"
SOURCE_URL = "https://www.fiawec.com/"

#: Season fallback when nothing else resolves it. Never used to claim a season
#: HAS run — `DEFAULT_SEASON` is a label, not an assertion about data.
DEFAULT_SEASON = 2026

#: The environment variable that overrides the season, matching every other
#: project's `<SPORT>_SEASON` convention.
SEASON_ENV = "WEC_SEASON"


def active_season() -> int:
    """Resolve the season: env → committed marker → literal default."""
    raw = os.environ.get(SEASON_ENV)
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    marker = DATA_DIR / "active_season.json"
    if marker.is_file():
        try:
            value = json.loads(marker.read_text()).get("season")
        except (OSError, json.JSONDecodeError):
            value = None
        if isinstance(value, int):
            return value
    return DEFAULT_SEASON


def snapshot_path(season: int) -> Path:
    """The committed snapshot that would be the offline source of truth.

    Downstream builds never touch the network — every implemented series in this
    repo reads a committed snapshot, so a flaky live source no-ops the run
    instead of publishing a degraded one. The file does not exist yet; the
    source below reports that rather than inventing its contents.
    """
    return DATA_DIR / f"official_{season}.json"


#: Whether a real data feed is wired. Read this rather than inferring liveness
#: from whether a call returned something.
DATA_SOURCE_IMPLEMENTED = False


__all__ = [
    "SPORT", "SHORT_NAME", "SLUG", "ACCENT", "COMPETITOR_UNIT", "CLASSES",
    "SOURCE_NAME", "SOURCE_URL", "DEFAULT_SEASON", "SEASON_ENV",
    "DATA_SOURCE_IMPLEMENTED", "PROJECT_ROOT", "DATA_DIR",
    "active_season", "snapshot_path",
]
