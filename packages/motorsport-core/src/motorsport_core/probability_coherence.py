"""Joint projection of nested top-k markets onto a coherent probability set.

The result conserves each market's expected number of finishers and enforces
P(win) <= P(podium) <= P(top-k) per competitor. This is a logical consistency
repair, not statistical recalibration or evidence of improved predictive skill.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np


def _ordered_rows(values: np.ndarray) -> np.ndarray:
    """Euclidean projection onto nondecreasing rows (pool adjacent violators)."""
    out = np.empty_like(values)
    for i, row in enumerate(values):
        blocks: list[tuple[float, int]] = []
        for value in row:
            blocks.append((float(value), 1))
            while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
                b, nb = blocks.pop()
                a, na = blocks.pop()
                blocks.append(((a * na + b * nb) / (na + nb), na + nb))
        out[i] = [mean for mean, count in blocks for _ in range(count)]
    return out


def coherent_top_k(
    probabilities: Sequence[Sequence[float]] | np.ndarray,
    targets: Sequence[float],
    *,
    floor: float = 0.0,
) -> np.ndarray:
    """Closest coherent matrix in squared distance, using Dykstra projections.

    Rows are competitors, columns are markets in increasing top-k order. All
    markets must describe the same field. Missing markets must be omitted by
    the caller rather than filled with zeros. Targets clamp to field size.
    """
    x = np.asarray(probabilities, dtype=float).copy()
    masses = np.asarray(targets, dtype=float)
    if x.ndim != 2 or masses.ndim != 1 or x.shape[1] != len(masses):
        raise ValueError('Expected competitors by markets and one target per market')
    if not np.isfinite(x).all() or not np.isfinite(masses).all():
        raise ValueError('Probabilities and targets must be finite')
    if (x < 0).any() or (x > 1).any() or (masses <= 0).any() or (np.diff(masses) < 0).any():
        raise ValueError('Probabilities must be in [0,1]; targets positive and ordered')
    if not np.isfinite(floor) or not 0 <= floor <= 1:
        raise ValueError('floor must be in [0,1]')
    if not x.size:
        return x
    masses = np.minimum(masses, x.shape[0])
    lower = min(floor, float(masses.min()) / x.shape[0])
    if (np.diff(x, axis=1) >= 0).all() and np.allclose(x.sum(axis=0), masses, atol=1e-10, rtol=0) and (x >= lower).all():
        return x
    row_correction = np.zeros_like(x)
    column_correction = np.zeros_like(x)
    for _ in range(4000):
        previous = x.copy()
        shifted = x + row_correction
        ordered = _ordered_rows(shifted)
        row_correction = shifted - ordered
        shifted = ordered + column_correction
        # Projection onto each bounded simplex, solved simultaneously by bisection.
        lo, hi = shifted.min(axis=0) - 1, shifted.max(axis=0) - lower
        for _ in range(55):
            mid = (lo + hi) / 2
            mass = np.clip(shifted - mid, lower, 1).sum(axis=0)
            lo = np.where(mass > masses, mid, lo)
            hi = np.where(mass > masses, hi, mid)
        x = np.clip(shifted - (lo + hi) / 2, lower, 1)
        column_correction = shifted - x
        if np.max(np.abs(x - previous)) < 1e-11 and (np.diff(x, axis=1) >= -1e-10).all():
            return x
    raise RuntimeError('Nested market projection did not converge; refusing incoherent output')
