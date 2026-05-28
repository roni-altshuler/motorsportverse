"""Regime classification + dispatch for the regime-routed 3-layer engine.

Phase 4 showed that a single continuous fusion function can't satisfy
all three season regimes at once: early needs damping, mid needs no
distribution compression, late needs full conversion influence. This
module replaces the single fusion call with a regime classifier that
dispatches to one of three specialised fusion strategies.

Routing is rule-based and leak-safe: it depends only on the target
round number, which is a known schedule fact. A learned-classifier
variant is documented but intentionally not built — the regime
boundaries (rounds 1-8 / 9-16 / 17+) are well-justified by the Phase 4
phase-breakdown evidence and there is no signal in the DB that would
help a learned router beat the rule.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

import numpy as np

from models.early_fusion import early_fusion
from models.late_fusion import late_fusion
from models.mid_fusion import mid_fusion


class Regime(str, Enum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"


# Boundary definitions (inclusive on both sides). Tuned on Phase 4 data;
# bumping these later doesn't require any other module changes.
EARLY_LAST_ROUND = 8
MID_LAST_ROUND = 16


def classify_regime(target_round: int) -> Regime:
    """Rule-based regime classifier. Pure function of the round number.

    * rounds 1-8  → EARLY
    * rounds 9-16 → MID
    * rounds 17+  → LATE

    Round numbers <= 0 default to EARLY (degenerate-input safety).
    """
    if target_round <= EARLY_LAST_ROUND:
        return Regime.EARLY
    if target_round <= MID_LAST_ROUND:
        return Regime.MID
    return Regime.LATE


_FUSION_BY_REGIME: dict[Regime, Callable[[np.ndarray, np.ndarray, float], np.ndarray]] = {
    Regime.EARLY: early_fusion,
    Regime.MID: mid_fusion,
    Regime.LATE: late_fusion,
}


def regime_fuse_one_stream(
    p_elite: np.ndarray,
    p_conv: np.ndarray,
    volatility: float,
    target_round: int,
) -> np.ndarray:
    """Dispatch a single probability stream through the regime fusion."""
    regime = classify_regime(target_round)
    fn = _FUSION_BY_REGIME[regime]
    return fn(p_elite, p_conv, volatility)


def regime_fuse_podium_and_win(
    p_elite_podium: np.ndarray,
    p_elite_win: np.ndarray,
    p_conv_podium: np.ndarray,
    p_conv_win: np.ndarray,
    volatility: float,
    target_round: int,
) -> tuple[np.ndarray, np.ndarray, Regime]:
    """Dispatch both probability streams through the regime fusion.

    Returns the fused podium and win probability arrays, plus the regime
    that was selected (for logging / reporting).
    """
    regime = classify_regime(target_round)
    fn = _FUSION_BY_REGIME[regime]
    p_pod = fn(p_elite_podium, p_conv_podium, volatility)
    p_win = fn(p_elite_win, p_conv_win, volatility)
    return p_pod, p_win, regime


__all__ = [
    "Regime",
    "EARLY_LAST_ROUND",
    "MID_LAST_ROUND",
    "classify_regime",
    "regime_fuse_one_stream",
    "regime_fuse_podium_and_win",
]
