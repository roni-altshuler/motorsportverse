"""Exponential time-decay sample weighting for Layer 1 training rows.

The Layer 1 ensemble (GBR + XGB + LSTM) currently fits every prior
training row with weight 1.0. With F1's small per-season sample size
(~22 rounds × 22 drivers), this means a row from 2024 Spa weighs the
same as a row from 2026 Monaco — even though the cars, tyres, and
regulations are different.

This module computes per-row weights from two compounded signals:

1. **Round recency** within the same season: exponential half-life
   in rounds. Default half-life = 8 rounds, ≈ a third of a season.

2. **Era distance** across seasons: multiplicative factor from
   :mod:`models.regulation_era`.

Weights are normalized so the mean is 1.0 (so the loss scale stays
comparable to an unweighted fit; XGBoost and GBR multiply per-row loss
by ``sample_weight``).

Floors are enforced: no row contributes less than ``min_weight``
(default 1e-3) so a single outlier season can't accidentally vanish
from the training set. The minimum is applied *before* normalization.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np

from .regulation_era import era_decay_factor


DEFAULT_HALF_LIFE_ROUNDS = 8.0
DEFAULT_MIN_WEIGHT = 1e-3
DEFAULT_ERA_MODE = "exponential"
DEFAULT_ERA_DECAY = 0.5


def round_decay_weight(
    row_season: int,
    row_round: int,
    current_season: int,
    current_round: int,
    *,
    half_life_rounds: float = DEFAULT_HALF_LIFE_ROUNDS,
) -> float:
    """Exponential time-decay weight from row age in rounds.

    Age is computed across season boundaries assuming 22 rounds/year.
    Past rows always have age > 0; future rows are not expected here
    (the caller is responsible for prior-only filtering) but if seen
    they get weight 1.0 to avoid silently amplifying leaks.
    """
    if half_life_rounds <= 0:
        raise ValueError(
            f"half_life_rounds must be positive; got {half_life_rounds}"
        )
    rounds_per_year = 22
    age = (current_season - row_season) * rounds_per_year + (
        current_round - row_round
    )
    if age <= 0:
        return 1.0
    return float(0.5 ** (age / half_life_rounds))


def compute_sample_weights(
    seasons: Iterable[int],
    rounds: Iterable[int],
    *,
    current_season: int,
    current_round: int,
    half_life_rounds: float = DEFAULT_HALF_LIFE_ROUNDS,
    era_mode: str = DEFAULT_ERA_MODE,
    era_decay: float = DEFAULT_ERA_DECAY,
    era_hard_cut: int = 1,
    min_weight: float = DEFAULT_MIN_WEIGHT,
    normalize: bool = True,
) -> np.ndarray:
    """Per-row sample weights combining round recency and era distance.

    ``len(seasons) == len(rounds) == len(out)``. Returns a 1-D float
    array. When ``normalize=True`` (the default) the mean of the output
    equals 1.0, so the unweighted-vs-weighted loss scale is comparable.

    The function is pure: same inputs → identical outputs.
    """
    s = np.asarray(list(seasons), dtype=np.int64)
    r = np.asarray(list(rounds), dtype=np.int64)
    if s.shape != r.shape:
        raise ValueError(
            f"seasons and rounds must have the same length; "
            f"got {s.shape} vs {r.shape}"
        )
    if s.size == 0:
        return np.array([], dtype=np.float64)

    round_w = np.array(
        [
            round_decay_weight(
                int(s_i),
                int(r_i),
                current_season,
                current_round,
                half_life_rounds=half_life_rounds,
            )
            for s_i, r_i in zip(s, r)
        ],
        dtype=np.float64,
    )
    era_w = np.array(
        [
            era_decay_factor(
                int(s_i),
                current_season,
                mode=era_mode,
                hard_cut_eras=era_hard_cut,
                decay=era_decay,
            )
            for s_i in s
        ],
        dtype=np.float64,
    )

    weights = np.clip(round_w * era_w, min_weight, None)
    if normalize and weights.sum() > 0:
        weights = weights * (len(weights) / weights.sum())
    return weights


__all__ = [
    "DEFAULT_HALF_LIFE_ROUNDS",
    "DEFAULT_MIN_WEIGHT",
    "DEFAULT_ERA_MODE",
    "DEFAULT_ERA_DECAY",
    "round_decay_weight",
    "compute_sample_weights",
]
