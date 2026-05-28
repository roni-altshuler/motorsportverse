"""Mid-season fusion strategy for the regime-routed engine.

Used for rounds 9-16 where Phase 4 showed the most damage from a global
shrinkage layer: winner-hit collapsed because pulling conversion probs
toward the elite-head mean flattened the top of the distribution.

Strategy: a *balanced* weighted blend with the conversion weight capped
at 50% and gated by ``(1 - V)``. No shrinkage. No mean-based correction.
The distribution shape from the elite head is preserved exactly; the
conversion model only nudges, never compresses.

Explicit non-features (per the Phase 5 brief):

* no shrinkage toward mean
* no mean-based correction
* no global maturity scalar
"""
from __future__ import annotations

import numpy as np


MID_CONVERSION_CAP = 0.5


def _safe(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    return np.where(np.isfinite(arr), arr, 0.0)


def mid_fusion(
    p_elite: np.ndarray,
    p_conv: np.ndarray,
    volatility: float,
    *,
    cap: float = MID_CONVERSION_CAP,
) -> np.ndarray:
    """Balanced mid-season fusion: pe + V-gated, capped conversion nudge.

    ``P_final = (1 - cap*(1-V)) * pe + cap*(1-V) * pc``

    At V=0 (predictable race): 50% pe + 50% pc (full ``cap`` influence).
    At V=1 (chaotic race): pure ``pe``.
    At V=0.5 (typical race): 75% pe + 25% pc.
    """
    pe = _safe(p_elite)
    pc = _safe(p_conv)
    v = float(np.clip(volatility, 0.0, 1.0))
    w_conv = cap * (1.0 - v)
    out = (1.0 - w_conv) * pe + w_conv * pc
    return np.clip(out, 0.0, 1.0)


__all__ = ["mid_fusion", "MID_CONVERSION_CAP"]
