"""Config-driven multi-season rollover.

Generalises the F1 project's ``scripts/season_rollover.py``: archive a
completed season's published data into a per-year subdirectory and start a
fresh active season. Sport-agnostic — the only inputs are the data root and the
set of files/dirs that constitute a season's published output.

Operations:
- :func:`archive_season` — snapshot active data into ``<root>/seasons/<year>/``.
- :func:`start_season` — record a new active year (validation hook for callers).
- :func:`auto_rollover` — archive + start when the active season is complete and
  a newer calendar exists.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Default published-season artefacts (mirrors the F1 layout); override per sport.
DEFAULT_SEASON_FILES = (
    "season.json",
    "standings.json",
    "season_tracker.json",
)
DEFAULT_SEASON_DIRS = (
    "rounds",
    "probabilities",
    "forward_eval",
)


@dataclass
class RolloverConfig:
    data_root: Path
    season_files: tuple[str, ...] = DEFAULT_SEASON_FILES
    season_dirs: tuple[str, ...] = DEFAULT_SEASON_DIRS
    archived: list[str] = field(default_factory=list)


def archive_season(config: RolloverConfig, year: int) -> Path:
    """Copy the active season's artefacts into ``seasons/<year>/``.

    Returns the archive directory. Missing artefacts are skipped (a partial
    season archives whatever exists), matching the F1 helper's tolerance.
    """
    root = Path(config.data_root)
    dest = root / "seasons" / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    for name in config.season_files:
        src = root / name
        if src.exists():
            shutil.copy2(src, dest / name)
            config.archived.append(name)
    for name in config.season_dirs:
        src = root / name
        if src.is_dir():
            shutil.copytree(src, dest / name, dirs_exist_ok=True)
            config.archived.append(name + "/")
    return dest


def start_season(config: RolloverConfig, year: int) -> dict:
    """Return the fresh active-season descriptor for ``year``.

    Callers persist this however they like (e.g. write ``season.json``). Kept
    side-effect-light so it's easy to test.
    """
    return {"year": year, "completed_rounds": [], "active": True}


def auto_rollover(
    config: RolloverConfig,
    active_year: int,
    active_complete: bool,
    available_years: list[int],
) -> dict | None:
    """If the active season is complete and a newer calendar exists, archive
    the active season and start the next. Returns the new season descriptor, or
    ``None`` when no rollover is warranted (hands-off / idempotent)."""
    newer = [y for y in available_years if y > active_year]
    if not (active_complete and newer):
        return None
    archive_season(config, active_year)
    return start_season(config, min(newer))


__all__ = [
    "RolloverConfig",
    "DEFAULT_SEASON_FILES",
    "DEFAULT_SEASON_DIRS",
    "archive_season",
    "start_season",
    "auto_rollover",
]
