#!/usr/bin/env python3
"""
generate_circuit_svg.py
========================
Build a minimal SVG track outline per circuit from FastF1 fastest-lap
telemetry, plus corner positions and DRS zone indices, and persist the
payload into ``website/public/data/rounds/round_NN.json`` under
``circuitInfo.geometry``.

The web app's ``CircuitMap`` React component consumes this directly,
which lets us replace the 6 MB of matplotlib speed-map PNGs and unrelated
Unsplash photos with a single ~5 KB monochrome vector per round that
shares one premium aesthetic across the entire site.

Pipeline per circuit:
  1. fastf1.get_session(year, gp, "R").load(laps, telemetry)
  2. lap.get_telemetry() → 1000+ (X, Y) points along the fastest lap
  3. Ramer-Douglas-Peucker simplify to ~120-200 vertices (visually
     identical at 600 px, ~98% length retention)
  4. Normalise into a 1000 × 1000 viewBox (centred, aspect-preserving)
  5. Project session.get_circuit_info() corners through the same xform
  6. Emit closed SVG path "M x0 y0 L x1 y1 …Z"
  7. Idempotent mutation of round JSON — only ``circuitInfo.geometry``
     is touched; all other keys stay byte-identical.

Failures (rate-limit, pre-2018 circuits, missing telemetry) leave the
geometry field as ``null`` so the consumer can fall back gracefully to
the cold-start matplotlib PNG.

Usage:
    python generate_circuit_svg.py --season 2026 --round 6
    python generate_circuit_svg.py --season 2026 --all-rounds
    python generate_circuit_svg.py --season 2026 --all-rounds --force
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    import fastf1
except ImportError:  # pragma: no cover
    sys.stderr.write("fastf1 is required (pip install fastf1)\n")
    raise SystemExit(1)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROUNDS_DIR = PROJECT_ROOT / "website" / "public" / "data" / "rounds"
CACHE_DIR = PROJECT_ROOT / "f1_cache"
SEASON_JSON = PROJECT_ROOT / "website" / "public" / "data" / "season.json"

VIEWBOX_SIZE = 1000  # 0 0 1000 1000
SIMPLIFY_RATIO = 0.004  # ε = 0.4% of track length (~12-18 m on a 4 km circuit)
MIN_LENGTH_RETENTION = 0.985  # halve ε if simplified length drops below this
COORD_DECIMALS = 1


# ── Ramer-Douglas-Peucker (numpy) ────────────────────────────────────────
def _perpendicular_distance(points: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """Distance from each point in ``points`` to the segment start→end."""
    if np.allclose(start, end):
        return np.linalg.norm(points - start, axis=1)
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)
    line_unit = line_vec / line_len
    delta = points - start
    proj_len = np.clip(delta @ line_unit, 0, line_len)
    foot = start + np.outer(proj_len, line_unit)
    return np.linalg.norm(points - foot, axis=1)


def rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Iterative Ramer-Douglas-Peucker. Returns the kept indices."""
    n = len(points)
    if n < 3:
        return np.arange(n)
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j - i < 2:
            continue
        segment = points[i + 1 : j]
        if len(segment) == 0:
            continue
        dists = _perpendicular_distance(segment, points[i], points[j])
        worst_local = int(np.argmax(dists))
        if dists[worst_local] > epsilon:
            worst = i + 1 + worst_local
            keep[worst] = True
            stack.append((i, worst))
            stack.append((worst, j))
    return np.where(keep)[0]


def _polyline_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))


# ── viewBox normalisation ─────────────────────────────────────────────────
class ViewTransform:
    """Affine that maps raw FastF1 ``(X, Y)`` telemetry into the 1000×1000
    SVG viewBox that ``build_geometry`` emits.

    The Y axis is flipped (telemetry is standard cartesian; SVG y grows
    downward), then the cloud is translated by its (flipped) bounding-box
    minimum, uniformly scaled so the long axis fills the box, and the short
    axis is centred. This is the single source of truth for the circuit
    coordinate frame: ``export_race_replay.py`` fits one of these from the
    same fastest-lap points and reuses it to project every car's position
    telemetry onto the same track, so cars are guaranteed to sit on the
    baked ``geometry.path``.
    """

    def __init__(self, mins: np.ndarray, scale: float, pad: np.ndarray) -> None:
        self.mins = mins  # on Y-flipped coords
        self.scale = scale
        self.pad = pad

    @property
    def metres_per_unit(self) -> float:
        return 1.0 / self.scale

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Project raw ``(X, Y)`` points (N×2) into viewBox space."""
        xy = np.asarray(points, dtype=np.float64).copy()
        xy[:, 1] = -xy[:, 1]
        return (xy - self.mins) * self.scale + self.pad


def fit_view_transform(points: np.ndarray, corners: np.ndarray | None) -> ViewTransform:
    """Fit a :class:`ViewTransform` from the geometry points (+corners bbox)."""
    xy = np.asarray(points, dtype=np.float64).copy()
    xy[:, 1] = -xy[:, 1]
    if corners is not None and len(corners):
        cc = np.asarray(corners, dtype=np.float64).copy()
        cc[:, 1] = -cc[:, 1]
        combined = np.vstack([xy, cc])
    else:
        combined = xy

    mins = combined.min(axis=0)
    maxs = combined.max(axis=0)
    extents = maxs - mins
    max_extent = float(max(extents))
    if max_extent <= 0:
        raise ValueError("degenerate telemetry: zero extent")
    scale = VIEWBOX_SIZE / max_extent
    pad = (VIEWBOX_SIZE - extents * scale) / 2.0
    return ViewTransform(mins, scale, pad)


def _normalise(points: np.ndarray, corners: np.ndarray | None) -> tuple[np.ndarray, np.ndarray | None, float]:
    """Translate + uniform-scale into a 0..VIEWBOX_SIZE square, centred.

    Thin wrapper over :func:`fit_view_transform` kept for the geometry
    pipeline's call site. Returns (xformed_points, xformed_corners,
    metres_per_unit).
    """
    transform = fit_view_transform(points, corners)
    xy_proj = transform.apply(points)
    cc_proj = transform.apply(corners) if corners is not None and len(corners) else None
    return xy_proj, cc_proj, transform.metres_per_unit


def _build_path(points: np.ndarray) -> str:
    parts = [f"M {points[0,0]:.{COORD_DECIMALS}f} {points[0,1]:.{COORD_DECIMALS}f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.{COORD_DECIMALS}f} {y:.{COORD_DECIMALS}f}")
    parts.append("Z")
    return " ".join(parts)


# ── DRS zone derivation ───────────────────────────────────────────────────
def _drs_zone_indices(distance_axis: np.ndarray, marshal_lights, kept_indices: np.ndarray) -> list[dict]:
    """Best-effort DRS-zone index ranges, projected onto the simplified path.

    FastF1's ``circuit_info`` doesn't always carry explicit DRS zones; this
    function is intentionally tolerant — returns an empty list when the data
    isn't usable rather than failing the whole circuit.
    """
    zones: list[dict] = []
    if marshal_lights is None or len(marshal_lights) == 0:
        return zones
    # Some FastF1 versions expose ``marshal_lights`` as a DataFrame with
    # a "Distance" column. We can't reliably know which ranges are DRS
    # without per-circuit metadata, so just skip when unsure.
    try:
        if "Distance" not in marshal_lights.columns:
            return zones
    except AttributeError:
        return zones
    return zones  # placeholder — fed through the cold-start fallback


# ── FastF1 → geometry ─────────────────────────────────────────────────────
def _load_telemetry(year: int, gp_key: str):
    """Attempt to load FastF1 session telemetry. Returns (tel, info) or None.

    Future races have no telemetry yet, so we walk back one season at a time
    (down to a 5-season window) looking for the same circuit's most recent
    completed running. Circuit layouts rarely change year-over-year.
    """
    for candidate_year in (year, year - 1, year - 2, year - 3):
        try:
            session = fastf1.get_session(candidate_year, gp_key, "R")
            session.load(laps=True, telemetry=True, weather=False, messages=False)
            lap = session.laps.pick_fastest()
            tel = lap.get_telemetry()
            if tel is not None and len(tel) >= 50:
                info = session.get_circuit_info()
                if candidate_year != year:
                    print(f"    using {candidate_year} layout for {gp_key} (no {year} data yet)")
                return tel, info
        except Exception as exc:  # noqa: BLE001
            print(f"    skip {candidate_year}: {exc}")
            continue
    return None


def geometry_from_telemetry(tel, info) -> tuple[dict[str, Any], "ViewTransform"] | None:
    """Build the geometry payload + its :class:`ViewTransform` from a loaded
    fastest-lap telemetry frame and circuit info.

    Split out of :func:`build_geometry` so callers that already hold a loaded
    session (e.g. ``export_race_replay.py``) can reuse the identical geometry
    core *and* obtain the transform needed to project car positions into the
    same viewBox — without a second FastF1 session load.
    """
    raw_xy = np.column_stack([tel["X"].values, tel["Y"].values]).astype(np.float64)

    # Filter NaNs and dedupe consecutive coords
    mask = np.isfinite(raw_xy).all(axis=1)
    raw_xy = raw_xy[mask]
    if len(raw_xy) < 50:
        print(f"    skip: too few finite points after filter ({len(raw_xy)})")
        return None

    diffs = np.diff(raw_xy, axis=0)
    keep_mask = np.concatenate([[True], np.any(np.abs(diffs) > 1e-3, axis=1)])
    raw_xy = raw_xy[keep_mask]

    track_length = _polyline_length(raw_xy)
    if track_length <= 0:
        print("    skip: zero track length")
        return None

    epsilon = track_length * SIMPLIFY_RATIO
    kept = rdp(raw_xy, epsilon)
    simplified = raw_xy[kept]
    # Validate length retention; tighten ε once if too aggressive
    if _polyline_length(simplified) / track_length < MIN_LENGTH_RETENTION:
        epsilon *= 0.5
        kept = rdp(raw_xy, epsilon)
        simplified = raw_xy[kept]

    # Corners
    corners_xy: np.ndarray | None = None
    corner_meta: list[dict] = []
    try:
        corners_df = info.corners if info is not None else None
        if corners_df is not None and len(corners_df):
            cx = corners_df["X"].values.astype(np.float64)
            cy = corners_df["Y"].values.astype(np.float64)
            corners_xy = np.column_stack([cx, cy])
            for _, row in corners_df.iterrows():
                corner_meta.append(
                    {
                        "number": int(row.get("Number", 0)),
                        "name": str(row.get("Name", "")) or None,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        print(f"    warn: circuit_info.corners unavailable ({exc})")
        corners_xy = None

    # Normalise points + corners into the 1000x1000 viewBox. Fit the transform
    # once so it can be returned for reuse (car-position projection).
    try:
        transform = fit_view_transform(simplified, corners_xy)
    except ValueError as exc:
        print(f"    skip: normalise failed ({exc})")
        return None
    proj_points = transform.apply(simplified)
    proj_corners = transform.apply(corners_xy) if corners_xy is not None and len(corners_xy) else None

    path = _build_path(proj_points)

    corner_payload: list[dict] = []
    if proj_corners is not None:
        for idx, ((x, y), meta) in enumerate(zip(proj_corners, corner_meta)):
            corner_payload.append(
                {
                    "number": meta.get("number") or (idx + 1),
                    "x": round(float(x), COORD_DECIMALS),
                    "y": round(float(y), COORD_DECIMALS),
                    "name": meta.get("name"),
                }
            )

    geometry = {
        "viewBox": f"0 0 {VIEWBOX_SIZE} {VIEWBOX_SIZE}",
        "path": path,
        "corners": corner_payload,
        "drsZones": [],
        "metresPerUnit": round(transform.metres_per_unit, 4),
        "source": "fastf1",
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    return geometry, transform


def build_geometry(year: int, gp_key: str) -> dict[str, Any] | None:
    """Returns the geometry payload for one circuit, or None on failure."""
    print(f"  • {year} R{gp_key}: loading FastF1 session…")
    loaded = _load_telemetry(year, gp_key)
    if loaded is None:
        print(f"    skip: no usable telemetry found in {year} or recent prior seasons")
        return None
    tel, info = loaded
    result = geometry_from_telemetry(tel, info)
    if result is None:
        return None
    geometry, _transform = result
    return geometry


# ── Round JSON I/O ────────────────────────────────────────────────────────
def _round_path(round_num: int) -> Path:
    return ROUNDS_DIR / f"round_{round_num:02d}.json"


def _load_round(round_num: int) -> dict | None:
    p = _round_path(round_num)
    if not p.exists():
        return None
    with p.open() as f:
        return json.load(f)


def _save_round(round_num: int, data: dict) -> None:
    p = _round_path(round_num)
    with p.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _resolve_gp_key(round_num: int) -> tuple[str, int] | None:
    """Look up the gpKey + season for a round from season.json."""
    if not SEASON_JSON.exists():
        return None
    with SEASON_JSON.open() as f:
        season = json.load(f)
    year = int(season.get("season", 2026))
    for entry in season.get("calendar", []):
        if int(entry.get("round", -1)) == round_num:
            gp_key = entry.get("gpKey") or entry.get("name")
            if gp_key:
                return (str(gp_key), year)
    return None


def process_round(round_num: int, season_override: int | None, force: bool) -> bool:
    data = _load_round(round_num)
    if data is None:
        print(f"  skip: round_{round_num:02d}.json not found")
        return False

    circuit_info = data.get("circuitInfo")
    if circuit_info is None:
        circuit_info = {}
        data["circuitInfo"] = circuit_info

    if not force and isinstance(circuit_info.get("geometry"), dict):
        print(f"  round {round_num}: geometry already present (use --force to refresh)")
        return True

    resolved = _resolve_gp_key(round_num)
    if resolved is None:
        print(f"  skip: cannot resolve gpKey for round {round_num}")
        return False
    gp_key, season_year = resolved
    if season_override is not None:
        season_year = season_override

    geometry = build_geometry(season_year, gp_key)

    if geometry is None:
        # Telemetry unreachable (rate-limit, CI egress block, pre-2018 circuit).
        # The layout is immutable, so NEVER clobber a previously-derived geometry
        # with null — that would blank an already-good track map.  Only write
        # null on a genuine cold start (no geometry yet).
        if isinstance(circuit_info.get("geometry"), dict):
            print(f"  round {round_num}: telemetry unavailable — keeping existing geometry")
            return True
        circuit_info["geometry"] = None
        _save_round(round_num, data)
        print(f"  round {round_num}: geometry=null (cold-start fallback in UI)")
        return False

    circuit_info["geometry"] = geometry
    _save_round(round_num, data)
    print(
        f"  round {round_num}: ok  vertices≈{geometry['path'].count('L') + 1}  "
        f"corners={len(geometry['corners'])}  bytes={len(geometry['path'])}"
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=None,
                        help="Override season year (defaults to value in season.json)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--round", type=int, help="Process a single round")
    group.add_argument("--all-rounds", action="store_true",
                       help="Process every round JSON under public/data/rounds/")
    parser.add_argument("--force", action="store_true",
                        help="Re-derive geometry even when already present")
    args = parser.parse_args(argv)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    if args.round:
        process_round(args.round, args.season, args.force)
        return 0

    files = sorted(ROUNDS_DIR.glob("round_*.json"))
    if not files:
        print("no round files found")
        return 1
    for p in files:
        try:
            num = int(p.stem.split("_")[-1])
        except ValueError:
            continue
        process_round(num, args.season, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
