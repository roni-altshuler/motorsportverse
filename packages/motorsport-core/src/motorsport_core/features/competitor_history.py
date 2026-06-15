"""Per-(driver, circuit) historical performance features.

Why this exists
---------------
The legacy feature set has scalar per-circuit attributes
(``CircuitOvertaking``, ``CircuitSafetyCar``, etc.) shared by every
driver. Nothing encodes that Verstappen is historically 0.3 s faster
than the field at Suzuka, or that Norris's wet pace at Spa is poor.

This module computes per-(driver, circuit) features strictly from races
prior to ``current_round`` and merges them onto the predicted-race frame.
Designed to be a clean, side-effect-free function — no global state, no
class — so it slots into ``build_training_dataset`` and the live
inference path the same way.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CircuitDriverHistoryConfig:
    lookback_seasons: int = 5
    last_k_visits: int = 4


def attach_circuit_driver_history(
    rows: pd.DataFrame,
    *,
    historical: pd.DataFrame,
    circuit_key: str,
    current_season: int,
    current_round: int,
    config: CircuitDriverHistoryConfig = CircuitDriverHistoryConfig(),
) -> pd.DataFrame:
    """Add per-(driver, circuit) features to ``rows``.

    Columns added (all NaN-imputed to field-mean downstream):

    * ``CircuitFinishMeanK`` — mean finish position over last ``last_k_visits``
      visits to this circuit (any season ≤ lookback window).
    * ``CircuitPodiumRate`` — fraction of past visits ending in P1-P3.
    * ``CircuitDNFRate`` — fraction of past visits ending in DNF (position 21+).
    * ``CircuitGridDelta`` — mean (grid - finish) over past visits, positive
      means the driver tends to gain places at this circuit.
    * ``CircuitVisits`` — count of historical visits (clipped to 0..lookback*1).
    """
    out = rows.copy()
    blank = float("nan")
    for col in (
        "CircuitFinishMeanK",
        "CircuitPodiumRate",
        "CircuitDNFRate",
        "CircuitGridDelta",
        "CircuitVisits",
    ):
        out[col] = blank

    if historical is None or historical.empty or "Driver" not in out.columns:
        return out
    needed = {"Driver", "Season", "Round", "CircuitKey", "FinishPosition"}
    if not needed.issubset(historical.columns):
        return out

    df = historical
    same_circuit = df["CircuitKey"] == circuit_key
    earlier_season = df["Season"] < current_season
    same_season_earlier = (df["Season"] == current_season) & (df["Round"] < current_round)
    in_window = df["Season"] >= (current_season - config.lookback_seasons)
    scoped = df[same_circuit & in_window & (earlier_season | same_season_earlier)]
    if scoped.empty:
        return out

    grouped = scoped.sort_values(["Season", "Round"]).groupby("Driver")

    per_driver: dict[str, dict[str, float]] = {}
    for driver, frame in grouped:
        tail = frame.tail(config.last_k_visits)
        finishes = tail["FinishPosition"].astype(float).to_numpy()
        finishes = finishes[np.isfinite(finishes)]
        if len(finishes) == 0:
            continue
        podium_rate = float(np.mean(finishes <= 3))
        dnf_rate = float(np.mean(finishes >= 21))  # informal DNF marker
        grid_delta = blank
        if "GridPosition" in tail.columns:
            grids = tail["GridPosition"].astype(float).to_numpy()
            valid = np.isfinite(grids) & np.isfinite(tail["FinishPosition"].astype(float).to_numpy())
            if np.any(valid):
                grid_delta = float(
                    np.mean(grids[valid] - tail["FinishPosition"].astype(float).to_numpy()[valid])
                )
        per_driver[driver] = {
            "CircuitFinishMeanK": float(np.mean(finishes)),
            "CircuitPodiumRate": podium_rate,
            "CircuitDNFRate": dnf_rate,
            "CircuitGridDelta": grid_delta,
            "CircuitVisits": float(min(len(frame), config.lookback_seasons + 1)),
        }

    for col in (
        "CircuitFinishMeanK",
        "CircuitPodiumRate",
        "CircuitDNFRate",
        "CircuitGridDelta",
        "CircuitVisits",
    ):
        out[col] = out["Driver"].map(lambda d, c=col: per_driver.get(d, {}).get(c, blank))

    return out
