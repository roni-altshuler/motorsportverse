"""Maturity-weighted adaptive fusion for the 3-layer probabilistic engine.

The Phase 3 fixed-fusion formula:

::

    P_final = (1 - V) * P_elite + V * P_conv   ("v_for_conversion" mode)

over-trusts the conversion model in early-season cold-start regimes
because the conversion priors are sparse / noisy there. This module
replaces that with a per-driver adaptive fusion gated by a maturity
score m in [0, 1] (see :mod:`models.maturity`):

::

    effective_V_per_driver = maturity * V
    P_conv_shrunk         = maturity * P_conv + (1 - maturity) * shrinkage_prior
    P_final               = (1 - effective_V) * P_elite + effective_V * P_conv_shrunk

Behaviour at the limits:

* m = 0: effective_V = 0 AND P_conv_shrunk = shrinkage_prior, so
  ``P_final = P_elite`` (conversion neutralised entirely).
* m = 1: effective_V = V AND P_conv_shrunk = P_conv, so the result is
  exactly the fixed-fusion formula.

A separate hard-cutoff overlay forces ``P_final[i] = P_elite[i]`` when
the driver has fewer than ``min_history_threshold`` prior races. This
catches rookies / sub drivers who get a tiny smooth maturity from the
career floor but should be treated as cold-start regardless.

The shrinkage prior is the elite head's own mean across the field
(``mean(p_elite)``) rather than a static constant. This means low-maturity
drivers get pulled toward a neutral-but-elite-aware probability instead
of an external prior that doesn't know the current race context.
"""
from __future__ import annotations

import numpy as np


def _safe_array(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.0)
    return arr


def adaptive_fusion(
    p_elite: np.ndarray,
    p_conv: np.ndarray,
    volatility: float,
    maturity: np.ndarray,
    *,
    min_history_threshold: int = 3,
    n_prior_per_driver: np.ndarray | None = None,
    shrinkage_prior: float | None = None,
) -> np.ndarray:
    """Maturity-weighted probability fusion.

    Parameters
    ----------
    p_elite, p_conv
        Per-driver probability arrays from the elite head and the conversion
        head respectively. Same shape, driver-aligned.
    volatility
        Scalar V in [0, 1] from the volatility model. Clipped defensively.
    maturity
        Per-driver maturity in [0, 1] (see :mod:`models.maturity`).
    min_history_threshold
        Hard cut-off: drivers with fewer than this many prior races bypass
        the smooth fusion and receive ``p_elite[i]`` exactly.
    n_prior_per_driver
        Optional per-driver count used by the hard-cutoff overlay. When
        ``None``, the hard cutoff is skipped.
    shrinkage_prior
        Optional scalar prior to shrink the conversion probability toward
        at low maturity. When ``None`` (the default), the elite head's
        per-call mean is used.

    Returns
    -------
    p_final : np.ndarray
        Same shape as the inputs. Raw probabilities (NOT renormalised
        — call :func:`models.probabilistic_combine.renormalize_probabilities`
        afterwards).
    """
    pe = _safe_array(p_elite)
    pc = _safe_array(p_conv)
    m = _safe_array(maturity)
    m = np.clip(m, 0.0, 1.0)
    v = float(np.clip(volatility, 0.0, 1.0))

    if shrinkage_prior is None:
        prior = float(pe.mean()) if len(pe) > 0 else 0.0
    else:
        prior = float(shrinkage_prior)

    effective_v = m * v
    pc_shrunk = m * pc + (1.0 - m) * prior
    p_final = (1.0 - effective_v) * pe + effective_v * pc_shrunk

    if n_prior_per_driver is not None:
        n_prior = np.asarray(n_prior_per_driver, dtype=int)
        cutoff_mask = n_prior < int(min_history_threshold)
        p_final = np.where(cutoff_mask, pe, p_final)

    p_final = np.clip(p_final, 0.0, 1.0)
    return p_final


def adaptive_fuse_podium_and_win(
    p_elite_podium: np.ndarray,
    p_elite_win: np.ndarray,
    p_conv_podium: np.ndarray,
    p_conv_win: np.ndarray,
    volatility: float,
    maturity: np.ndarray,
    *,
    min_history_threshold: int = 3,
    n_prior_per_driver: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Convenience wrapper: apply :func:`adaptive_fusion` to both the
    podium and win streams with the elite-head per-call means as the
    respective shrinkage priors.
    """
    p_final_pod = adaptive_fusion(
        p_elite_podium,
        p_conv_podium,
        volatility=volatility,
        maturity=maturity,
        min_history_threshold=min_history_threshold,
        n_prior_per_driver=n_prior_per_driver,
        shrinkage_prior=None,  # uses mean(p_elite_podium)
    )
    p_final_win = adaptive_fusion(
        p_elite_win,
        p_conv_win,
        volatility=volatility,
        maturity=maturity,
        min_history_threshold=min_history_threshold,
        n_prior_per_driver=n_prior_per_driver,
        shrinkage_prior=None,  # uses mean(p_elite_win)
    )
    return p_final_pod, p_final_win


__all__ = ["adaptive_fusion", "adaptive_fuse_podium_and_win"]
