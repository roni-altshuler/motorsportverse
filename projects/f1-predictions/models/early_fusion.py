"""Early-season (cold-start) fusion strategy for the regime-routed engine.

Used for rounds 1-8 where:

* conversion priors are sparse and unstable (early-season noise)
* elite-head pace-anchored ordering is the most reliable signal
* the system should *barely* listen to the conversion model

Strategy: cap the conversion weight at 15% of total, and route that cap
through ``(1 - V)`` so chaotic races (high V) make conversion DROP to
zero. In a perfectly predictable race (V=0) the conversion model still
caps at 15% influence — small enough that early-season noise can't
overwhelm the pace anchor.

Explicit non-features (per the Phase 5 brief):

* no shrinkage toward mean
* no mean-based correction
* no global maturity scalar
"""
from __future__ import annotations

import numpy as np


EARLY_CONVERSION_CAP = 0.15


def _safe(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    return np.where(np.isfinite(arr), arr, 0.0)


def early_fusion(
    p_elite: np.ndarray,
    p_conv: np.ndarray,
    volatility: float,
    *,
    cap: float = EARLY_CONVERSION_CAP,
) -> np.ndarray:
    """Cold-start fusion: pe-dominant with capped, V-gated conversion weight.

    ``P_final = (1 - cap*(1-V)) * pe + cap*(1-V) * pc``

    At V=0 (predictable race): conversion gets ``cap`` weight (15% by default).
    At V=1 (chaotic race): conversion gets 0; result is pure ``pe``.
    """
    pe = _safe(p_elite)
    pc = _safe(p_conv)
    v = float(np.clip(volatility, 0.0, 1.0))
    w_conv = cap * (1.0 - v)
    out = (1.0 - w_conv) * pe + w_conv * pc
    return np.clip(out, 0.0, 1.0)


__all__ = ["early_fusion", "EARLY_CONVERSION_CAP"]
