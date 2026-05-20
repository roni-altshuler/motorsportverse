"""Glue between the trained race-pace ensemble and a live race weekend.

Why this exists
---------------
Step 3 of the A-P1.1 push.  The race simulator in
``models/race_simulator.py`` takes a grid + race-pace artefacts + context
and returns market probabilities, but it doesn't know anything about the
project's existing pipeline (``apply_race_postprocessing``, the FastF1
calendar, ``CIRCUIT_CHARACTERISTICS``, etc.).  This module bridges them.

Public surface
--------------
``run_simulator_for_round(season, round_num, gp_key, merged, weather,
total_laps, ...)`` — the single entry point ``export_website_data.py``
calls.  Returns a dict ready to splice into the round payload, or
``None`` when:
  - no trained race-pace model is in the registry yet, **or**
  - the registry is disabled via ``F1_REGISTRY_ENABLED=0``, **or**
  - any step in the load → grid-build → simulate path fails.

Falling through to ``None`` is intentional — the legacy
``apply_race_postprocessing`` formula remains the production path until
the simulator is trained, validated, and explicitly promoted.

Pure-additive
-------------
This module does not modify any existing file.  Callers opt in via the
``use_race_simulator=True`` kwarg on
``export_website_data.export_round_data``.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from models.race_simulator import (
    DEFAULT_N_SAMPLES,
    DEFAULT_SEED,
    DriverInitial,
    GridEntry,
    race_context_from_circuit,
    simulate_race,
)
from models.registry import ModelRegistry, registry_enabled

# Same sentinel ``train_race_pace.py`` uses.  Kept in sync via a module
# constant rather than importing the trainer (avoid pulling in argparse +
# scikit deps just to read one integer).
RACE_PACE_REGISTRY_ROUND: int = 99
RACE_PACE_METADATA_KIND: str = "race-pace"

LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def find_latest_race_pace_entry(
    registry: ModelRegistry | None = None,
) -> tuple[int, int, dict] | None:
    """Find the most recent race-pace ensemble in the registry.

    Returns ``(season, round, metadata)`` or ``None`` when no race-pace
    artefact has been registered (i.e. ``train_race_pace.py`` has not run
    yet).
    """
    reg = registry or ModelRegistry()
    entries = reg.list_all()
    race_pace_entries = [
        (s, r, m) for s, r, m in entries if m.get("kind") == RACE_PACE_METADATA_KIND
    ]
    if not race_pace_entries:
        return None
    # Sort by season-then-round so the most recent training run wins.
    race_pace_entries.sort(key=lambda row: (row[0], row[1]))
    return race_pace_entries[-1]


# --------------------------------------------------------------------------- #
# Grid + initials construction
# --------------------------------------------------------------------------- #


def _build_grid_and_initials(
    merged: pd.DataFrame,
) -> tuple[list[GridEntry], dict[str, DriverInitial]]:
    """Convert the export pipeline's ``merged`` DataFrame to a simulator
    grid + per-driver initial-condition map.

    Columns we read:
      * ``Driver``        — driver code (required)
      * ``Team``          — team name (required; ``UNK`` fallback)
      * ``GridPosition``  — quali-derived starting slot (1..N).  Falls back
        to ``QualifyingRank`` or row order when absent.
      * ``PredictedLapTime`` — per-driver mean lap time from the quali-time
        ensemble.  We derive ``base_pace_offset_s`` as the deviation from
        the grid mean so the fastest drivers carry a negative offset
        (faster) into the simulator's per-lap noise model.
    """
    if merged is None or len(merged) == 0:
        return [], {}

    # Resolve grid position with sensible fallbacks.
    if "GridPosition" in merged.columns:
        grid_pos = merged["GridPosition"]
    elif "QualifyingRank" in merged.columns:
        grid_pos = merged["QualifyingRank"]
    else:
        grid_pos = pd.Series(range(1, len(merged) + 1), index=merged.index)

    mean_pace = (
        float(merged["PredictedLapTime"].mean())
        if "PredictedLapTime" in merged.columns
        else 0.0
    )

    grid: list[GridEntry] = []
    initials: dict[str, DriverInitial] = {}
    for (_, row), pos in zip(merged.iterrows(), grid_pos):
        driver = str(row.get("Driver") or "").upper()
        if not driver:
            continue
        team = str(row.get("Team") or row.get("Constructor") or "UNK").upper()
        try:
            slot = int(pos)
        except (TypeError, ValueError):
            slot = len(grid) + 1
        grid.append(GridEntry(driver=driver, team=team, grid_position=slot))
        pace = row.get("PredictedLapTime")
        try:
            offset = float(pace) - mean_pace if pace is not None else 0.0
        except (TypeError, ValueError):
            offset = 0.0
        initials[driver] = DriverInitial(
            base_pace_offset_s=offset,
            starting_tyre="MEDIUM",  # v1: uniform default; per-driver strategy lands in v2
        )

    # Sort by grid slot so the simulator sees the actual starting order.
    grid.sort(key=lambda g: g.grid_position)
    return grid, initials


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def run_simulator_for_round(
    season: int,
    round_num: int,
    gp_key: str,
    merged: pd.DataFrame,
    weather: dict | None,
    total_laps: int,
    circuit_characteristics: dict,
    n_samples: int = DEFAULT_N_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any] | None:
    """Run the race simulator for the upcoming race.

    Returns a dict shaped for direct inclusion in the round JSON::

        {
            "applied": True,
            "n_samples": 2000,
            "n_laps": 78,
            "training_metadata": {...},
            "p_win":    {"VER": 0.34, "NOR": 0.27, ...},
            "p_podium": {"VER": 0.71, ...},
            "p_top6":   {...},
            "p_top10":  {...},
            "mean_finish": {"VER": 1.8, ...},
        }

    Returns ``None`` when the simulator can't run (no trained model,
    registry disabled, missing columns, etc.).  Caller treats ``None``
    as "fall through to the legacy projection formula".
    """
    if not registry_enabled():
        LOGGER.info("simulator runner: registry disabled, skipping")
        return None

    registry = ModelRegistry()
    entry = find_latest_race_pace_entry(registry)
    if entry is None:
        LOGGER.info(
            "simulator runner: no race-pace model in registry; "
            "run train_race_pace.py first"
        )
        return None

    training_season, training_round, training_meta = entry
    try:
        loaded = registry.load(training_season, training_round)
    except Exception as exc:  # noqa: BLE001 — registry IO is best-effort
        LOGGER.warning("simulator runner: registry load failed: %s", exc)
        return None

    encoders = training_meta.get("encoders") or {}
    feature_cols = training_meta.get("feature_columns") or []
    ensemble_weights = training_meta.get("ensemble_weights") or {"gbr": 0.5, "xgb": 0.5}
    artifacts = {
        "gbr": loaded.get("race_pace_gbr"),
        "xgb": loaded.get("race_pace_xgb"),
        "feature_columns": feature_cols,
        "ensemble_weights": ensemble_weights,
    }
    if artifacts["gbr"] is None or artifacts["xgb"] is None:
        LOGGER.warning(
            "simulator runner: registry entry missing gbr/xgb artefacts; "
            "skip"
        )
        return None

    grid, initials = _build_grid_and_initials(merged)
    if not grid:
        LOGGER.info("simulator runner: empty grid from merged DataFrame; skip")
        return None

    context = race_context_from_circuit(
        season=season,
        round_num=round_num,
        circuit_key=gp_key,
        total_laps=total_laps,
        circuit_characteristics=circuit_characteristics,
        weather=weather,
    )

    try:
        out = simulate_race(
            grid=grid,
            artifacts=artifacts,
            encoders=encoders,
            context=context,
            initials=initials,
            n_samples=n_samples,
            seed=seed,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the pipeline
        LOGGER.warning("simulator runner: simulate_race failed: %s", exc)
        return None

    return {
        "applied": True,
        "n_samples": out.n_samples,
        "n_laps": out.n_laps,
        "trained_season": training_season,
        "trained_round": training_round,
        "training_metrics": training_meta.get("metrics", {}),
        "p_win": out.p_win,
        "p_podium": out.p_podium,
        "p_top6": out.p_top6,
        "p_top10": out.p_top10,
        "mean_finish": out.mean_finish_position,
    }
