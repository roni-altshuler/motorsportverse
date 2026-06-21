"""Elite-signal features for the podium/winner classifier heads.

The baseline `predicted_position` ordering stored in
`data/history.duckdb` produces a noisy top-of-the-grid. Re-ranking on
top of that ordering using only signals derived from the same
`predicted_lap_time` cannot break the podium-hit / winner-hit ceiling
because it adds no new information about which drivers are elite
race-winners.

This module engineers driver-level prior-only features designed to
expose elite-signal: how often this driver lands on the podium, how
often they win, and how strongly they have over-performed at this
circuit historically. Every aggregation is strictly prior to the target
(season, round) — enforced via :func:`leakage.assert_seasons_prior_only`
at the boundary.

Entry point
-----------
:func:`build_elite_features` takes the full historical frame
``history_df`` plus a target ``(season, round)``, and returns a
driver-level feature frame for that one round. The feature frame is
keyed by driver and carries:

* `driver_podium_rate_5`        — fraction of last 5 races (across
                                   seasons, prior-only) where this
                                   driver finished P1-P3. NaN if <3
                                   prior races.
* `driver_podium_rate_season`   — same, current season only, prior
                                   rounds only.
* `driver_winner_rate_season`   — fraction of P1 finishes in prior
                                   season rounds.
* `driver_circuit_podium_rate`  — fraction of prior visits to this
                                   circuit where driver finished P1-P3.
                                   NaN if <2 prior visits.
* `qualifying_dominance`        — gap (in lap-time seconds) from this
                                   driver's predicted_lap_time to the
                                   next-faster driver in this round.
                                   Positive when this driver is slower
                                   than the next-faster; 0.0 for pole.
* `predicted_position`          — baseline ordering (the head needs to
                                   know where the regressor placed
                                   them).
* `predicted_lap_time_rank`     — rank-encoded predicted_lap_time
                                   (1=pole). Identical to
                                   predicted_position for most rounds
                                   but kept separate for cases where
                                   they diverge (different
                                   tie-breaking).

A team-level feature was considered (``team_podium_rate_5``) but is
skipped: the project ships a driver→team mapping only for the *active*
season (2026), not historical. Applying it to 2024/2025 silently
misattributes drivers (HAM was Mercedes in 2024, not Ferrari). Skipped
here to avoid confounding from team changes; if a per-season team map
lands later, this can be revisited.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from leakage import assert_seasons_prior_only


# Map of round-number → circuit key, lifted from benchmark_models.ROUND_TO_GP_KEY.
# Duplicated here so this module stays standalone (avoids a benchmark<->model
# import cycle).
ROUND_TO_GP_KEY: dict[int, dict[int, str]] = {
    2018: {},
    2019: {},
    2020: {},
    2021: {},
    2022: {},
    2023: {
        1: "Bahrain", 2: "Saudi Arabia", 3: "Australia", 4: "Azerbaijan",
        5: "Miami", 6: "Monaco", 7: "Spain", 8: "Canada", 9: "Austria",
        10: "Great Britain", 11: "Hungary", 12: "Belgium", 13: "Netherlands",
        14: "Italy", 15: "Singapore", 16: "Japan", 17: "Qatar",
        18: "United States", 19: "Mexico", 20: "Brazil", 21: "Las Vegas",
        22: "Abu Dhabi",
    },
    2024: {
        1: "Bahrain", 2: "Saudi Arabia", 3: "Australia", 4: "Japan",
        5: "China", 6: "Miami", 7: "Emilia Romagna", 8: "Monaco",
        9: "Canada", 10: "Spain", 11: "Austria", 12: "Great Britain",
        13: "Hungary", 14: "Belgium", 15: "Netherlands", 16: "Italy",
        17: "Azerbaijan", 18: "Singapore", 19: "United States", 20: "Mexico",
        21: "Brazil", 22: "Las Vegas", 23: "Qatar", 24: "Abu Dhabi",
    },
    2025: {
        1: "Australia", 2: "China", 3: "Japan", 4: "Bahrain",
        5: "Saudi Arabia", 6: "Miami", 7: "Emilia Romagna", 8: "Monaco",
        9: "Spain", 10: "Canada", 11: "Austria", 12: "Great Britain",
        13: "Belgium", 14: "Hungary", 15: "Netherlands", 16: "Italy",
        17: "Azerbaijan", 18: "Singapore", 19: "United States", 20: "Mexico",
        21: "Brazil", 22: "Las Vegas", 23: "Qatar", 24: "Abu Dhabi",
    },
}


# Required columns for history_df.
_REQUIRED_COLS = {
    "season", "round", "driver", "predicted_position",
    "actual_position", "predicted_lap_time",
}


FEATURE_COLUMNS = (
    "driver_podium_rate_5",
    "driver_podium_rate_season",
    "driver_winner_rate_season",
    "driver_circuit_podium_rate",
    "qualifying_dominance",
    "predicted_position",
    "predicted_lap_time_rank",
)


def _gp_key(season: int, round_: int) -> str:
    return ROUND_TO_GP_KEY.get(season, {}).get(round_, f"R{round_:02d}")


def _safe_rate(numerator: int, denominator: int, min_denom: int) -> float:
    if denominator < min_denom:
        return float("nan")
    return float(numerator) / float(denominator)


def _driver_podium_rate_recent(
    driver_history: pd.DataFrame, window: int = 5, min_races: int = 3
) -> float:
    """Last-N prior races (across seasons, in chronological order).

    Returns NaN if the driver has fewer than ``min_races`` prior races.
    """
    if driver_history.empty:
        return float("nan")
    # Already filtered to prior-only and sorted by (season, round)
    tail = driver_history.tail(window)
    if len(tail) < min_races:
        return float("nan")
    podiums = int((tail["actual_position"] <= 3).sum())
    return float(podiums) / float(len(tail))


def _driver_podium_rate_in_season(
    driver_history: pd.DataFrame, season: int
) -> float:
    """Fraction of prior rounds in this season where driver was on the podium.

    Returns NaN if the driver has no prior rounds in this season.
    """
    sub = driver_history[driver_history["season"] == season]
    if sub.empty:
        return float("nan")
    return float((sub["actual_position"] <= 3).sum()) / float(len(sub))


def _driver_winner_rate_in_season(
    driver_history: pd.DataFrame, season: int
) -> float:
    """Fraction of prior rounds in this season where driver won.

    Returns NaN if the driver has no prior rounds in this season.
    """
    sub = driver_history[driver_history["season"] == season]
    if sub.empty:
        return float("nan")
    return float((sub["actual_position"] == 1).sum()) / float(len(sub))


def _driver_circuit_podium_rate(
    driver_history: pd.DataFrame, target_gp_key: str, min_visits: int = 2
) -> float:
    """Fraction of prior visits to ``target_gp_key`` where driver was on
    the podium. NaN if <``min_visits`` prior visits.

    Uses the round→circuit map; rounds with no mapping (1950s sparse
    seasons) won't match any target gp_key and are silently skipped.
    """
    if not target_gp_key or driver_history.empty:
        return float("nan")
    gp_keys = [
        _gp_key(int(s), int(r))
        for s, r in zip(driver_history["season"], driver_history["round"])
    ]
    mask = np.array([k == target_gp_key for k in gp_keys])
    if mask.sum() < min_visits:
        return float("nan")
    sub = driver_history[mask]
    return float((sub["actual_position"] <= 3).sum()) / float(len(sub))


def _qualifying_dominance(
    df: pd.DataFrame, driver: str
) -> float:
    """Gap (seconds) from this driver's predicted_lap_time to the
    next-faster driver in the round.

    The fastest driver (pole on predicted lap time) gets 0.0; everyone
    else gets a positive gap measuring how far they are behind the
    next-faster driver. Captures the "lonely fast driver" effect: a
    pole-sitter who is far ahead of P2 has a larger dominance signal
    coming from P2's gap to them; a tightly packed top-3 has small
    gaps throughout.
    """
    if df.empty or driver not in df["driver"].values:
        return float("nan")
    sub = df[["driver", "predicted_lap_time"]].dropna()
    if sub.empty:
        return float("nan")
    sub = sub.sort_values("predicted_lap_time").reset_index(drop=True)
    idx_arr = sub.index[sub["driver"] == driver].tolist()
    if not idx_arr:
        return float("nan")
    idx = idx_arr[0]
    if idx == 0:
        return 0.0  # pole — no faster driver
    me = float(sub.loc[idx, "predicted_lap_time"])
    ahead = float(sub.loc[idx - 1, "predicted_lap_time"])
    return me - ahead


def build_elite_features(
    history_df: pd.DataFrame,
    target_season: int,
    target_round: int,
) -> pd.DataFrame:
    """Build a per-driver elite-feature frame for one round.

    Parameters
    ----------
    history_df
        Full historical frame with columns
        {season, round, driver, predicted_position, actual_position,
        predicted_lap_time}. Rows for (target_season, target_round)
        must be present (we need predicted_lap_time + predicted_position
        for the current frame); all other rows are used for prior-only
        aggregation.
    target_season, target_round
        The round we're building features for.

    Returns
    -------
    pd.DataFrame
        One row per driver in the target round, with columns
        ``FEATURE_COLUMNS`` plus ``driver``, ``season``, ``round``.
        Order matches the target-round frame sorted by
        ``predicted_position``.
    """
    missing = _REQUIRED_COLS - set(history_df.columns)
    if missing:
        raise ValueError(
            f"history_df missing required columns: {sorted(missing)}"
        )

    # Boundary leakage check on the *prior* frame.
    prior_full = history_df[
        ~(
            (history_df["season"] > target_season)
            | (
                (history_df["season"] == target_season)
                & (history_df["round"] >= target_round)
            )
        )
    ].copy()
    # Drop rows without a settled actual finishing position (can't be used
    # in any podium/winner aggregation).
    prior = prior_full[prior_full["actual_position"].notna()].copy()
    prior["season"] = prior["season"].astype(int)
    prior["round"] = prior["round"].astype(int)
    prior["actual_position"] = prior["actual_position"].astype(int)
    prior = prior.sort_values(["season", "round"]).reset_index(drop=True)

    # Assert at the boundary.
    assert_seasons_prior_only(
        prior[["season", "round"]].to_dict("records"),
        current_season=target_season,
        current_round=target_round,
        label=f"elite_features prior for ({target_season},{target_round})",
    )

    target = history_df[
        (history_df["season"] == target_season)
        & (history_df["round"] == target_round)
    ].copy()
    if target.empty:
        return pd.DataFrame(columns=("driver", "season", "round", *FEATURE_COLUMNS))

    target = target.sort_values("predicted_position").reset_index(drop=True)
    target_gp = _gp_key(target_season, target_round)

    # Pre-compute predicted_lap_time rank on the target frame.
    target["predicted_lap_time_rank"] = (
        target["predicted_lap_time"].rank(method="min", ascending=True)
    )

    rows: list[dict] = []
    for _, r in target.iterrows():
        driver = str(r["driver"])
        driver_hist = prior[prior["driver"] == driver]
        feats = {
            "driver": driver,
            "season": target_season,
            "round": target_round,
            "driver_podium_rate_5": _driver_podium_rate_recent(driver_hist),
            "driver_podium_rate_season": _driver_podium_rate_in_season(
                driver_hist, target_season
            ),
            "driver_winner_rate_season": _driver_winner_rate_in_season(
                driver_hist, target_season
            ),
            "driver_circuit_podium_rate": _driver_circuit_podium_rate(
                driver_hist, target_gp
            ),
            "qualifying_dominance": _qualifying_dominance(target, driver),
            "predicted_position": float(r["predicted_position"])
            if pd.notna(r["predicted_position"])
            else float("nan"),
            "predicted_lap_time_rank": float(r["predicted_lap_time_rank"]),
        }
        rows.append(feats)

    return pd.DataFrame(rows)


def build_elite_features_batch(
    history_df: pd.DataFrame,
    target_rounds: Iterable[tuple[int, int]],
) -> pd.DataFrame:
    """Convenience: build elite features for many rounds at once.

    Returns the concatenation; each per-round build runs through the
    full leak-safe path.
    """
    parts: list[pd.DataFrame] = []
    for season, round_ in target_rounds:
        feats = build_elite_features(history_df, season, round_)
        if not feats.empty:
            parts.append(feats)
    if not parts:
        return pd.DataFrame(
            columns=("driver", "season", "round", *FEATURE_COLUMNS)
        )
    return pd.concat(parts, ignore_index=True)


__all__ = [
    "FEATURE_COLUMNS",
    "build_elite_features",
    "build_elite_features_batch",
]
