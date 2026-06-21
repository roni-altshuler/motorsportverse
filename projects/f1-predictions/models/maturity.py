"""Data-maturity scoring for the probabilistic fusion layer.

The Phase 3 benchmark showed the probabilistic_three_layer pipeline winning
2025 (where every driver has 24+ prior races of conversion history) but
losing 2024 (where the conversion model has near-zero history for the first
~8 rounds). This module quantifies per-driver "is the conversion prior
trustworthy?" so the fusion logic can gate accordingly.

Output: maturity m in [0, 1] per (driver, target_season, target_round).

* m = 0.0 -> no usable prior history; conversion model is pure noise
* m = 1.0 -> driver has at least ``full_maturity_at`` prior races (recent
  season) AND enough career history; conversion model can be trusted

Formula
-------
::

    m_recent  = min(n_prior_in_target_season / full_maturity_at, 1.0)
    m_career  = min(n_prior_all_history / 24, 1.0)
    maturity  = 0.7 * m_recent + 0.3 * m_career

Recent-season history dominates because driver form changes year-over-year
(rookies, team switches, regulation eras). The career term avoids treating
veteran drivers as cold-start at the start of a fresh season.

All aggregations are STRICTLY prior to (target_season, target_round) and
enforced at the boundary via :func:`leakage.assert_seasons_prior_only`.
"""
from __future__ import annotations

import pandas as pd

from leakage import assert_seasons_prior_only


FULL_MATURITY_AT_DEFAULT = 8  # races of recent-season history for full m_recent
CAREER_SATURATION = 24        # races of career history for full m_career


def _prior_frame(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
) -> pd.DataFrame:
    """Return rows strictly prior to (target_season, target_round) with a
    settled actual_position. Asserts leak-protection at the boundary."""
    if history_df.empty:
        return history_df
    df = history_df.copy()
    df["season"] = df["season"].astype(int)
    df["round"] = df["round"].astype(int)
    mask = ~(
        (df["season"] > target_season)
        | (
            (df["season"] == target_season)
            & (df["round"] >= target_round)
        )
    )
    prior = df.loc[mask].copy()
    if "actual_position" in prior.columns:
        prior = prior[prior["actual_position"].notna()].copy()
    if not prior.empty:
        assert_seasons_prior_only(
            prior[["season", "round"]].to_dict("records"),
            current_season=target_season,
            current_round=target_round,
            label=f"maturity prior for ({target_season},{target_round})",
        )
    return prior


def compute_driver_maturity(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
    driver: str,
    *,
    full_maturity_at: int = FULL_MATURITY_AT_DEFAULT,
    career_saturation: int = CAREER_SATURATION,
) -> float:
    """Returns m in [0, 1] reflecting confidence in this driver's conversion priors.

    See module docstring for the formula. ``history_df`` must contain
    columns season, round, driver, actual_position.
    """
    prior = _prior_frame(history_df, target_season, target_round)
    if prior.empty:
        return 0.0

    driver_prior = prior[prior["driver"] == driver]
    n_total = int(len(driver_prior))
    n_season = int(
        len(driver_prior[driver_prior["season"] == target_season])
    )

    m_recent = min(n_season / float(max(1, full_maturity_at)), 1.0)
    m_career = min(n_total / float(max(1, career_saturation)), 1.0)
    return float(0.7 * m_recent + 0.3 * m_career)


def compute_maturity_frame(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
    drivers: list[str],
    *,
    full_maturity_at: int = FULL_MATURITY_AT_DEFAULT,
    career_saturation: int = CAREER_SATURATION,
) -> pd.DataFrame:
    """Vectorised maturity for a list of drivers.

    Returns a frame with columns: driver, maturity, n_prior_races_total,
    n_prior_races_current_season. One row per input driver, preserving order.
    """
    prior = _prior_frame(history_df, target_season, target_round)
    rows: list[dict] = []
    for d in drivers:
        if prior.empty:
            rows.append(
                {
                    "driver": d,
                    "maturity": 0.0,
                    "n_prior_races_total": 0,
                    "n_prior_races_current_season": 0,
                }
            )
            continue
        d_prior = prior[prior["driver"] == d]
        n_total = int(len(d_prior))
        n_season = int(len(d_prior[d_prior["season"] == target_season]))
        m_recent = min(n_season / float(max(1, full_maturity_at)), 1.0)
        m_career = min(n_total / float(max(1, career_saturation)), 1.0)
        m = float(0.7 * m_recent + 0.3 * m_career)
        rows.append(
            {
                "driver": d,
                "maturity": m,
                "n_prior_races_total": n_total,
                "n_prior_races_current_season": n_season,
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "FULL_MATURITY_AT_DEFAULT",
    "CAREER_SATURATION",
    "compute_driver_maturity",
    "compute_maturity_frame",
]
