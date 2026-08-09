#!/usr/bin/env python3
"""
replay_geometry.py
==================
Reconstruct a **smooth, high-fidelity circuit outline** for a Race Theatre replay
directly from the replay payload's own per-frame car positions — no FastF1, no
network. Pure NumPy, deterministic, idempotent.

Why this exists
---------------
The original ``geometry.path`` was a Ramer-Douglas-Peucker simplification of a
single fastest-lap trace (``generate_circuit_svg.SIMPLIFY_RATIO = 0.4%``). At that
epsilon a 4-7 km circuit collapses to **24-44 straight segments** — corners become
polygonal and, on a couple of circuits (Hungaroring), the simplification even
back-tracked, so the drawn track no longer resembled the real layout.

The replay already ships every car's real GPS position, projected into the same
0..1000 viewBox as the outline, for every second of the race. One clean green lap
of the race leader is therefore a *topologically exact* trace of the circuit in the
exact coordinate frame the cars animate in. We low-pass it (Fourier truncation —
the natural smoother for a closed loop) to remove GPS jitter while preserving every
corner, and emit a dense (~380-point) path.

The core (:func:`high_fidelity_path`) operates purely on the replay *payload dict*,
so it is reused two ways:
  * ``export_race_replay.build_replay`` calls it as the final geometry step, so
    freshly baked replays are born high-fidelity.
  * ``rebuild_replay_geometry.py`` applies it to the already-committed replays.

Because it reads only ``cars`` / ``stints`` / ``finish`` / ``totalLaps`` (all baked
from the same FastF1 session that produced the coarse path), the result is
identical whether baked fresh or rebuilt offline.
"""
from __future__ import annotations

from typing import Any

import numpy as np

# Kept in sync with export_race_replay / slim_replays: the on-screen frame is the
# 0..1000 viewBox, so 1 dp on x/y is sub-pixel.
COORD_DECIMALS = 1
DEFAULT_POINTS = 380      # emitted outline vertices (renderer strokes straight segs)
DEFAULT_HARMONICS = 46    # Fourier harmonics kept — enough for hairpins, kills jitter
RESAMPLE_N = 720          # working resolution before the low-pass


def _car_xy(car: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([v if v is not None else np.nan for v in car.get("x", [])], dtype=float)
    y = np.array([v if v is not None else np.nan for v in car.get("y", [])], dtype=float)
    return x, y


def _interior_laps(stints: list[dict[str, Any]] | None) -> set[int]:
    """Laps strictly inside a stint — excludes each stint's first & last lap
    (the out-/in-laps that route through the pit lane and distort the S/F area)."""
    ok: set[int] = set()
    for s in stints or []:
        a, b = int(s.get("startLap", 0)), int(s.get("endLap", -1))
        ok.update(range(a + 1, b))
    return ok


def _bridge_nans(a: np.ndarray) -> np.ndarray:
    n = len(a)
    idx = np.arange(n)
    ok = np.isfinite(a)
    if ok.sum() < 2:
        return a
    return np.interp(idx, idx[ok], a[ok])


def _resample_closed(pts: np.ndarray, n: int) -> np.ndarray:
    """Uniform arc-length resample of a closed polyline to exactly ``n`` points."""
    p = np.vstack([pts, pts[:1]])
    seg = np.sqrt((np.diff(p, axis=0) ** 2).sum(axis=1))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total <= 0:
        return np.repeat(pts[:1], n, axis=0)
    u = np.linspace(0.0, total, n, endpoint=False)
    x = np.interp(u, s, p[:, 0])
    y = np.interp(u, s, p[:, 1])
    return np.column_stack([x, y])


def _fourier_lowpass_closed(pts: np.ndarray, keep: int) -> np.ndarray:
    """Keep only the first ``keep`` Fourier harmonics of the periodic x(t)/y(t)
    signals — the natural low-pass for a closed curve."""
    n = len(pts)
    fx = np.fft.rfft(pts[:, 0])
    fy = np.fft.rfft(pts[:, 1])
    k = min(keep, len(fx) - 1)
    fx[k + 1:] = 0
    fy[k + 1:] = 0
    x = np.fft.irfft(fx, n)
    y = np.fft.irfft(fy, n)
    return np.column_stack([x, y])


def _reference_code(payload: dict[str, Any]) -> str | None:
    """The car whose clean lap we trace: prefer the winner, fall back to the car
    with the most on-track frames (robust to a sparse leader trace)."""
    cars = payload.get("cars") or {}
    finish = payload.get("finish") or []
    if finish:
        code = finish[0].get("code")
        if code in cars:
            x, _ = _car_xy(cars[code])
            if np.isfinite(x).sum() >= 40:
                return code
    best, best_n = None, 0
    for code, car in cars.items():
        n = int(np.isfinite(_car_xy(car)[0]).sum())
        if n > best_n:
            best, best_n = code, n
    return best if best_n >= 40 else None


def _pick_green_lap(lap: np.ndarray, run: np.ndarray, candidates: set[int]) -> int | None:
    """Among candidate laps pick a fast (green-pace) one with the best GPS coverage.
    Green laps sit near the minimum frame-count; SC/red-flag laps run long and are
    excluded, so the traced outline follows the racing line, not a crawl."""
    counts = {L: int(((lap == L) & run).sum()) for L in candidates}
    counts = {L: c for L, c in counts.items() if c >= 25}
    if not counts:
        return None
    fastest = min(counts.values())
    near_green = {L: c for L, c in counts.items() if c <= 1.35 * fastest}

    def coverage(L: int) -> float:
        m = lap == L
        return float(run[m].mean()) if m.any() else 0.0

    return max(near_green, key=lambda L: (coverage(L), -abs(counts[L] - fastest)))


def _build_path(points: np.ndarray, decimals: int) -> str:
    parts = [f"M {points[0, 0]:.{decimals}f} {points[0, 1]:.{decimals}f}"]
    parts += [f"L {x:.{decimals}f} {y:.{decimals}f}" for x, y in points[1:]]
    parts.append("Z")
    return " ".join(parts)


# Corners are baked from the geometry session's circuit_info. When that session had
# to fall back to a prior season's layout (no clean current-year trace), its
# coordinate frame can differ from the current-year car positions the outline is now
# rebuilt from — so the corner pills would float off-track. Good circuits land their
# corners within ~2-8 units of the outline; anything past this tolerance is a frame
# mismatch and the pills are dropped rather than drawn in the wrong place.
CORNER_ALIGN_TOL = 15.0


def _parse_path_points(path: str) -> np.ndarray:
    import re

    nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", path)]
    return np.array(nums, dtype=float).reshape(-1, 2) if nums else np.empty((0, 2))


def _median_corner_distance(path: str, corners: list[dict[str, Any]]) -> float:
    """Median nearest-vertex distance from each corner to the outline (viewBox
    units). Large ⇒ corners live in a different projection frame than the outline."""
    pts = _parse_path_points(path)
    if len(pts) == 0 or not corners:
        return 0.0
    dists = [
        float(np.min(np.hypot(pts[:, 0] - c["x"], pts[:, 1] - c["y"])))
        for c in corners
        if c.get("x") is not None and c.get("y") is not None
    ]
    return float(np.median(dists)) if dists else 0.0


def apply_high_fidelity_geometry(payload: dict[str, Any]) -> bool:
    """Rebuild ``payload['geometry']['path']`` in place from the car positions and
    prune corner pills that don't sit on the resulting outline (prior-year frame
    mismatch). Returns True if anything changed. Safe no-op when reconstruction
    isn't possible — the existing geometry is left untouched.
    """
    geo = payload.get("geometry")
    if not isinstance(geo, dict):
        return False
    new_path = high_fidelity_path(payload)
    if new_path is None:
        return False
    changed = new_path != geo.get("path")
    geo["path"] = new_path
    corners = geo.get("corners") or []
    if corners and _median_corner_distance(new_path, corners) > CORNER_ALIGN_TOL:
        geo["corners"] = []
        changed = True
    return changed


def high_fidelity_path(
    payload: dict[str, Any],
    *,
    n_out: int = DEFAULT_POINTS,
    keep: int = DEFAULT_HARMONICS,
    decimals: int = COORD_DECIMALS,
) -> str | None:
    """Return a smooth ``"M x y L x y … Z"`` outline reconstructed from the
    payload's car positions, or ``None`` if the payload can't yield one (caller
    then keeps whatever path it already had).

    Deterministic and idempotent: same payload → byte-identical path.
    """
    cars = payload.get("cars") or {}
    stints = payload.get("stints") or {}
    total_laps = int(payload.get("totalLaps") or 0)

    ref = _reference_code(payload)
    if ref is None:
        return None

    x, y = _car_xy(cars[ref])
    lap = np.asarray(cars[ref].get("lap") or [], dtype=int)
    if len(lap) != len(x) or len(x) == 0:
        return None
    run = np.isfinite(x) & np.isfinite(y)

    candidates = _interior_laps(stints.get(ref))
    if not candidates:
        hi = total_laps - 1 if total_laps > 2 else int(lap.max() if len(lap) else 0)
        candidates = set(range(2, max(3, hi)))

    best_lap = _pick_green_lap(lap, run, candidates)
    if best_lap is None:
        return None

    m = lap == best_lap
    xs = _bridge_nans(np.where(run, x, np.nan)[m])
    ys = _bridge_nans(np.where(run, y, np.nan)[m])
    trace = np.column_stack([xs, ys])
    if len(trace) < 20 or not np.isfinite(trace).all():
        return None

    loop = _resample_closed(trace, RESAMPLE_N)
    loop = _fourier_lowpass_closed(loop, keep=keep)
    loop = _resample_closed(loop, n_out)
    if not np.isfinite(loop).all():
        return None
    return _build_path(loop, decimals)
