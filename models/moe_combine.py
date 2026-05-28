"""Combine multiple expert probability streams via MoE gate weights.

Companion to :mod:`models.moe_gate`. Given:

* K per-driver P(win) arrays (one per expert)
* K per-driver P(podium) arrays
* K gate weights from :class:`models.moe_gate.LearnedGate`

Produces the fused P(win) and P(podium) arrays.

This is intentionally a tiny helper — the heavy lifting is in
``moe_gate.LearnedGate``. Keeping it separate makes the combine step
easy to unit-test and easy to swap if the gate architecture changes.
"""
from __future__ import annotations

import numpy as np


def fuse_with_gate(
    expert_p_win: np.ndarray,
    expert_p_pod: np.ndarray,
    gate_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Mixture fusion of K expert streams.

    Parameters
    ----------
    expert_p_win, expert_p_pod
        Shape (K, n_drivers). Each row is one expert's per-driver
        probability array.
    gate_weights
        Shape (K,). Must sum to 1.0 (within float tolerance); not
        re-normalised here.

    Returns
    -------
    (p_win, p_podium) — each shape (n_drivers,).
    """
    pw = np.asarray(expert_p_win, dtype=float)
    pp = np.asarray(expert_p_pod, dtype=float)
    w = np.asarray(gate_weights, dtype=float)
    if pw.ndim != 2 or pp.ndim != 2:
        raise ValueError("expert arrays must be 2-D (K, n_drivers)")
    if w.ndim != 1 or w.shape[0] != pw.shape[0]:
        raise ValueError(
            f"gate_weights shape {w.shape} incompatible with K={pw.shape[0]}"
        )
    p_win = (w[:, None] * pw).sum(axis=0)
    p_pod = (w[:, None] * pp).sum(axis=0)
    return np.clip(p_win, 0.0, 1.0), np.clip(p_pod, 0.0, 1.0)


__all__ = ["fuse_with_gate"]
