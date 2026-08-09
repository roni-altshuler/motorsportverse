"""CI-safe tests for the offline Race Theatre geometry reconstruction.

No FastF1, no network — a synthetic replay payload (cars driving a known circle for
several laps) exercises :func:`replay_geometry.high_fidelity_path` and asserts the
emitted outline is a valid, smooth, closed loop that recovers the underlying shape.
Also guards idempotence and the "unavailable → None" fallback contract.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from replay_geometry import apply_high_fidelity_geometry, high_fidelity_path  # noqa: E402


def _parse(path: str) -> np.ndarray:
    nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?", path)]
    return np.array(nums).reshape(-1, 2)


def _polygon_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _synthetic_replay(n_laps: int = 6, pts_per_lap: int = 120, seed: int = 0) -> dict:
    """A circle centred in the viewBox, driven for `n_laps`, with a touch of GPS
    jitter — a stand-in for a real leader's trace in a baked replay payload."""
    rng = np.random.default_rng(seed)
    cx = cy = 500.0
    r = 340.0
    xs: list[float] = []
    ys: list[float] = []
    laps: list[int] = []
    for lap in range(1, n_laps + 1):
        theta = np.linspace(0, 2 * math.pi, pts_per_lap, endpoint=False)
        jitter = rng.normal(0, 3.0, size=(pts_per_lap, 2))
        xs.extend((cx + r * np.cos(theta) + jitter[:, 0]).tolist())
        ys.extend((cy + r * np.sin(theta) + jitter[:, 1]).tolist())
        laps.extend([lap] * pts_per_lap)
    car = {"x": xs, "y": ys, "lap": laps, "gap": None}
    return {
        "totalLaps": n_laps,
        "finish": [{"code": "AAA", "position": 1}],
        "cars": {"AAA": car},
        "stints": {"AAA": [{"compound": "MEDIUM", "startLap": 1, "endLap": n_laps}]},
        "geometry": {"path": "M 0 0 L 1 1 Z"},
    }


def test_recovers_smooth_closed_loop():
    payload = _synthetic_replay()
    path = high_fidelity_path(payload)
    assert path is not None
    assert path.startswith("M ") and path.rstrip().endswith("Z")
    pts = _parse(path)
    # dense outline (not the old 24-44 point polygon)
    assert len(pts) >= 200
    # closed loop with real enclosed area (didn't collapse or back-track)
    assert _polygon_area(pts) > 0.4 * (1000 ** 2) * 0.1  # circle r=340 → area ~0.36e6
    # stays inside the viewBox
    assert pts.min() > -50 and pts.max() < 1050
    # recovers a circle: radius roughly constant around the centroid
    c = pts.mean(axis=0)
    radii = np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1])
    assert radii.std() / radii.mean() < 0.06  # <6% radial variation → smooth ring


def test_deterministic_and_idempotent():
    p1 = high_fidelity_path(_synthetic_replay())
    p2 = high_fidelity_path(_synthetic_replay())
    assert p1 == p2  # deterministic: no RNG, no clock


def test_smoother_than_raw_jitter():
    """Consecutive-segment direction changes should be small — i.e. genuinely
    smoothed, not a jagged connect-the-dots of noisy samples."""
    pts = _parse(high_fidelity_path(_synthetic_replay(seed=3)))
    d = np.diff(np.vstack([pts, pts[:1]]), axis=0)
    ang = np.arctan2(d[:, 1], d[:, 0])
    turn = np.abs(np.diff(np.unwrap(ang)))
    assert np.median(turn) < 0.15  # radians per segment — a gentle, smooth curve


def test_keeps_aligned_corners_drops_misaligned():
    # Aligned corners (on the circle) survive; a frame-mismatched set is pruned.
    payload = _synthetic_replay()
    payload["geometry"] = {"path": "M 0 0 Z", "corners": [
        {"number": 1, "x": 840.0, "y": 500.0},   # on the ring (centre 500, r≈340)
        {"number": 2, "x": 500.0, "y": 840.0},
    ]}
    assert apply_high_fidelity_geometry(payload) is True
    assert len(payload["geometry"]["corners"]) == 2  # aligned → kept
    assert payload["geometry"]["path"].startswith("M ")

    payload2 = _synthetic_replay()
    payload2["geometry"] = {"path": "M 0 0 Z", "corners": [
        {"number": 1, "x": 20.0, "y": 20.0},      # nowhere near the ring
        {"number": 2, "x": 60.0, "y": 950.0},
    ]}
    apply_high_fidelity_geometry(payload2)
    assert payload2["geometry"]["corners"] == []   # off-track → dropped


def test_none_when_unavailable():
    # No usable car data → contract is to return None (caller keeps existing path).
    assert high_fidelity_path({"totalLaps": 0, "finish": [], "cars": {}, "stints": {}}) is None
    sparse = {
        "totalLaps": 3,
        "finish": [{"code": "AAA"}],
        "cars": {"AAA": {"x": [1.0, None], "y": [2.0, None], "lap": [1, 1]}},
        "stints": {"AAA": []},
    }
    assert high_fidelity_path(sparse) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
