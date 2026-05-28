"""Probability fusion — the top of the 3-layer probabilistic engine.

Given:

* Layer 1 (``elite_head_plus_hybrid``): an ordering and the elite-head
  P(win) + P(podium) per driver — the *pace-anchored* probability view.
* Layer 2 (volatility model): a scalar V in [0, 1] for the round —
  high V = chaotic race, racecraft matters more than pace.
* Layer 3 (conversion model): per-driver P_conv(win), P_conv(podium)
  capturing historical conversion-from-projected-grid.

This module fuses them. The high-level intuition: when V is HIGH, the
race is chaotic and pace-ordering predicts the actual finish less
reliably; the conversion model (which captures racecraft, gains/losses
on race day, circuit-specific conversion) should dominate. When V is
LOW, the race is qualifying-locked and the elite pace ordering should
dominate.

Default fusion math
-------------------
::

    P_final(podium) = (1 - V) * P_elite(podium) + V * P_conv(podium)
    P_final(win)    = (1 - V) * P_elite(win)    + V * P_conv(win)

i.e. V is the weight given to the conversion view. We expose
:func:`fuse_probabilities(..., fusion: Literal["v_for_conversion",
"v_for_elite"])` so the benchmark can run both directions and pick
empirically. ``"v_for_conversion"`` is the default per the brief's
sanity-check rewrite.

After fusion the per-round probabilities are renormalized:

* P(win) is divided by the per-round sum so it sums to 1.0 (a race
  has one winner).
* P(podium) is rescaled to sum to 3.0 across the field (three
  podium slots).

Re-ranking
----------
:func:`rerank_with_probabilistic` takes the Layer 1 anchor ordering
and re-sorts the top-6 by ``P_final(podium)``. Positions 7-22 keep
their Layer 1 ordering. This mirrors :func:`benchmark_models._rerank_top_n_by_elite`
so the production-wiring story is identical.
"""
from __future__ import annotations

from typing import Literal

import numpy as np


FusionMode = Literal["v_for_conversion", "v_for_elite"]


def _safe_array(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    arr = np.where(np.isfinite(arr), arr, 0.0)
    return arr


def fuse_probabilities(
    p_elite_podium: np.ndarray,
    p_elite_win: np.ndarray,
    p_conv_podium: np.ndarray,
    p_conv_win: np.ndarray,
    volatility: float,
    fusion: FusionMode = "v_for_conversion",
) -> tuple[np.ndarray, np.ndarray]:
    """Fuse elite + conversion probabilities under a volatility weight.

    Parameters
    ----------
    p_elite_podium, p_elite_win
        Per-driver probabilities from Layer 1 elite heads (already in
        the driver-aligned order of the current round frame).
    p_conv_podium, p_conv_win
        Per-driver probabilities from Layer 3 conversion heads, aligned
        to the same driver order.
    volatility
        Layer 2 V in [0, 1]. Clipped defensively.
    fusion
        ``"v_for_conversion"`` (default): high V → conversion dominates.
        ``"v_for_elite"``: high V → elite dominates (the inverted form,
        kept available so the benchmark can confirm direction).

    Returns
    -------
    (P_final_podium, P_final_win) — same shape as inputs. Each row is
    a driver. Values are RAW (not yet renormalized; call
    :func:`renormalize_probabilities`).
    """
    v = float(np.clip(volatility, 0.0, 1.0))
    pe_pod = _safe_array(p_elite_podium)
    pe_win = _safe_array(p_elite_win)
    pc_pod = _safe_array(p_conv_podium)
    pc_win = _safe_array(p_conv_win)
    if fusion == "v_for_conversion":
        w_conv = v
        w_elite = 1.0 - v
    elif fusion == "v_for_elite":
        w_conv = 1.0 - v
        w_elite = v
    else:
        raise ValueError(f"unknown fusion mode {fusion!r}")
    p_final_pod = w_elite * pe_pod + w_conv * pc_pod
    p_final_win = w_elite * pe_win + w_conv * pc_win
    # Defensive clip into [0, 1] before renormalization.
    p_final_pod = np.clip(p_final_pod, 0.0, 1.0)
    p_final_win = np.clip(p_final_win, 0.0, 1.0)
    return p_final_pod, p_final_win


def renormalize_probabilities(
    p_podium: np.ndarray,
    p_win: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Rescale so P(win) sums to 1.0 and P(podium) sums to 3.0 across drivers.

    If all-zero (degenerate input), return a uniform distribution.
    """
    p_win = _safe_array(p_win)
    p_pod = _safe_array(p_podium)
    n = len(p_win)
    if n == 0:
        return p_pod, p_win

    sum_win = float(p_win.sum())
    if sum_win > 0:
        p_win = p_win / sum_win
    else:
        p_win = np.ones(n, dtype=float) / float(n)

    sum_pod = float(p_pod.sum())
    if sum_pod > 0:
        p_pod = p_pod * (3.0 / sum_pod)
    else:
        p_pod = np.full(n, 3.0 / float(n), dtype=float)
    # Cap individual podium probability at 1.0 (a driver can't be more
    # than 100% likely to be on the podium).
    p_pod = np.clip(p_pod, 0.0, 1.0)
    return p_pod, p_win


def rerank_with_probabilistic(
    anchor_order: np.ndarray,
    p_final_podium: np.ndarray,
    top_n: int = 6,
) -> np.ndarray:
    """Re-rank the top-N of an anchor ordering by P_final(podium).

    Mirrors :func:`benchmark_models._rerank_top_n_by_elite` so the
    behaviour is identical to the established production-wiring
    recipe. Positions outside the top-N keep their anchor position.
    """
    anchor = np.asarray(anchor_order, dtype=float)
    n = len(anchor)
    if n == 0:
        return anchor.astype(int)
    sorted_idx = np.argsort(anchor, kind="stable")
    top_idx = sorted_idx[: min(top_n, n)]
    scores = p_final_podium[top_idx]
    # Higher P_final(podium) = better predicted finish.
    new_order_within_top = np.argsort(-scores, kind="stable")
    new_top_idx = top_idx[new_order_within_top]

    out = anchor.astype(float).copy()
    for rank_zero_based, idx in enumerate(new_top_idx):
        out[idx] = float(rank_zero_based + 1)

    # Convert to integer ranks 1..N with stable tie-breaking.
    order = np.argsort(out, kind="stable")
    ranks = np.empty_like(order, dtype=int)
    ranks[order] = np.arange(1, len(order) + 1)
    return ranks


# --------------------------------------------------------------------------- #
# Calibration / loss helpers used by the benchmark report
# --------------------------------------------------------------------------- #


def winner_log_loss(
    p_win_per_driver: np.ndarray,
    actual_winner_idx: int,
    epsilon: float = 1e-9,
) -> float:
    """Binary cross-entropy on the win prediction for one round.

    Returns -log(P_win[actual_winner_idx]) with epsilon clipping.
    """
    p = float(p_win_per_driver[actual_winner_idx])
    p = max(min(p, 1.0 - epsilon), epsilon)
    return -float(np.log(p))


def podium_log_loss(
    p_podium_per_driver: np.ndarray,
    actual_podium_mask: np.ndarray,
    epsilon: float = 1e-9,
) -> float:
    """Multi-label binary cross-entropy on podium for one round.

    Sums -log(P) for actual podium drivers and -log(1-P) for non-podium
    drivers, then normalizes by the number of drivers so different
    fields are comparable.
    """
    p = np.clip(p_podium_per_driver, epsilon, 1.0 - epsilon)
    y = actual_podium_mask.astype(float)
    losses = -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))
    if len(losses) == 0:
        return 0.0
    return float(losses.mean())


def calibration_error_10_bin(
    p_predictions: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Reliability gap on P(win): mean |predicted - empirical| per bucket,
    weighted by bucket sample count."""
    p = np.asarray(p_predictions, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if len(p) == 0:
        return 0.0
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    total_n = len(p)
    weighted_gap = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        # Include right edge on the last bin.
        if i == n_bins - 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        n_in = int(mask.sum())
        if n_in == 0:
            continue
        mean_p = float(p[mask].mean())
        emp = float(y[mask].mean())
        weighted_gap += abs(mean_p - emp) * (n_in / total_n)
    return float(weighted_gap)


__all__ = [
    "FusionMode",
    "fuse_probabilities",
    "renormalize_probabilities",
    "rerank_with_probabilistic",
    "winner_log_loss",
    "podium_log_loss",
    "calibration_error_10_bin",
]
