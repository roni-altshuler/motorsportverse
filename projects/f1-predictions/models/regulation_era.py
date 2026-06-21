"""Regulation-era awareness for F1 training windows.

F1 cars change shape every few years. Pre-2017 was the V6-hybrid era;
2017-2021 introduced wider cars; 2022-2025 was ground-effect; 2026
brings new power units, active aero, lighter cars. Treating lap times
across eras as comparable injects bias into any model trained on
pre-regulation-change data.

This module exposes a single source of truth for era boundaries and
two helpers used by the rest of the pipeline:

- :func:`era_of(season)` — which regulation era a season belongs to.
- :func:`era_decay_factor(...)` — multiplicative weight discounting
  rows from older eras.

The era table is intentionally conservative: only changes that altered
car dynamics enough to invalidate cross-era pace comparisons are
recorded. Wing-cap rule tweaks etc. are not era boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Era:
    """A regulation regime spanning a contiguous range of seasons.

    ``end_season`` is inclusive. ``None`` means "current open era".
    """

    name: str
    start_season: int
    end_season: int | None
    summary: str


ERAS: tuple[Era, ...] = (
    Era("v6_hybrid_intro", 2014, 2016,
        "V6 hybrid power units; narrow cars."),
    Era("wide_cars", 2017, 2021,
        "Wider cars + bigger tyres; mid-era halo + DRS tweaks."),
    Era("ground_effect", 2022, 2025,
        "Return of ground-effect floors; simplified aero."),
    Era("active_aero_2026", 2026, None,
        "New PU formula (≈50/50 ICE/ERS), active aero, lighter cars."),
)


# Hard-cut threshold: rows older than this many eras back contribute
# zero weight by default. Set to 1 — only the current era plus the
# immediately-preceding one ever contribute. Override per-caller.
DEFAULT_MAX_ERA_DISTANCE = 1


def era_of(season: int) -> Era:
    """Return the :class:`Era` that contains ``season``.

    Raises :class:`ValueError` for seasons before the first known era.
    """
    for era in ERAS:
        end = era.end_season if era.end_season is not None else season
        if era.start_season <= season <= end:
            return era
    raise ValueError(
        f"season {season} is older than the earliest tracked era "
        f"({ERAS[0].start_season}); update ERAS or filter earlier."
    )


def era_distance(season_a: int, season_b: int) -> int:
    """Number of era boundaries between two seasons.

    0 = same era; 1 = adjacent era; etc. Symmetric.
    """
    era_a = era_of(season_a)
    era_b = era_of(season_b)
    idx_a = ERAS.index(era_a)
    idx_b = ERAS.index(era_b)
    return abs(idx_a - idx_b)


def era_decay_factor(
    row_season: int,
    current_season: int,
    *,
    mode: str = "exponential",
    hard_cut_eras: int = DEFAULT_MAX_ERA_DISTANCE,
    decay: float = 0.5,
) -> float:
    """Multiplicative weight in [0, 1] for a row from ``row_season``.

    Three modes:

    - ``"hard_cut"``: 1.0 for rows within ``hard_cut_eras`` of current,
      0.0 otherwise. Useful for the 2026 regulation reset.
    - ``"exponential"``: ``decay ** era_distance``. Default.
    - ``"none"``: always 1.0 (use only for ablations / debugging).
    """
    if mode == "none":
        return 1.0
    dist = era_distance(row_season, current_season)
    if mode == "hard_cut":
        return 1.0 if dist <= hard_cut_eras else 0.0
    if mode == "exponential":
        return float(decay**dist)
    raise ValueError(
        f"unknown era-decay mode {mode!r}; "
        f"expected one of: hard_cut, exponential, none"
    )


__all__ = [
    "Era",
    "ERAS",
    "DEFAULT_MAX_ERA_DISTANCE",
    "era_of",
    "era_distance",
    "era_decay_factor",
]
