"""Late-season fusion strategy for the regime-routed engine.

Used for rounds 17+ where Phase 3/4 evidence showed the probabilistic
``v_for_elite`` fusion ran +12.5pp ahead of the incumbent on winner-hit
(31.2% vs 18.8%). Late season has stabilized driver hierarchies and
24+ rounds of conversion-rate history per driver — the conversion model
is now a reliable signal and should be given full weight.

Strategy: the original ``v_for_elite`` formula from Phase 3 — no caps,
no shrinkage, no mean-based correction.

::

    P_final = V * pe + (1 - V) * pc

At V=0 (predictable race): pure conversion.
At V=1 (chaotic race): pure elite.

Intuition: when racing conditions are chaotic the pace anchor remains
the most defensible prediction; when conditions are settled the
driver-specific racecraft history is the additional signal that pushes
prediction quality above pace alone.

Explicit non-features (per the Phase 5 brief):

* no shrinkage toward mean
* no mean-based correction
* no global maturity scalar
"""
from __future__ import annotations

import numpy as np


def _safe(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    return np.where(np.isfinite(arr), arr, 0.0)


def late_fusion(
    p_elite: np.ndarray,
    p_conv: np.ndarray,
    volatility: float,
) -> np.ndarray:
    """Full ``v_for_elite`` fusion: pe gated by V, pc gated by (1-V).

    ``P_final = V * pe + (1 - V) * pc``
    """
    pe = _safe(p_elite)
    pc = _safe(p_conv)
    v = float(np.clip(volatility, 0.0, 1.0))
    out = v * pe + (1.0 - v) * pc
    return np.clip(out, 0.0, 1.0)


__all__ = ["late_fusion"]
