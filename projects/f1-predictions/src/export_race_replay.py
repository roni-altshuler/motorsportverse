#!/usr/bin/env python3
"""
export_race_replay.py
=====================
Bake a time-sampled **race replay** for the Race Theatre surface on the F1
website from FastF1 telemetry, into
``website/public/data/replays/round_NN.json``.

The replay reconstructs where all 22 cars are on track over the whole race so
the browser can animate them:

  * **Positions** are the cars' *true* telemetry positions (``session.pos_data``)
    projected into the same 1000×1000 viewBox as the circuit outline, using the
    identical :class:`generate_circuit_svg.ViewTransform` that produced
    ``geometry.path`` — so every car sits on the track (real racing lines,
    side-by-side battles), not on a synthetic centre-line.
  * **Order / gaps** come from a per-car time-into-lap progress scalar (robust
    to the start/finish geometry offset), converted to a seconds gap-to-leader.
  * **Tyres** are the real stint/compound history; **flags** (yellow / Safety
    Car / VSC / red) are the real ``session.track_status`` timeline; the final
    **classification** is ``session.results``.

Like the circuit geometry and the lap cache, this **must be baked locally** —
FastF1's network is blocked from GitHub Actions runners. The committed JSON is
the offline source of truth that CI deploys; nothing re-derives it in CI.

Usage:
    python src/export_race_replay.py --round 10 --season 2026
    python src/export_race_replay.py --round 10 --dt 1.0
    python src/export_race_replay.py --all-completed          # every scored round
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import fastf1
except ImportError:  # pragma: no cover
    sys.stderr.write("fastf1 is required (pip install fastf1)\n")
    raise SystemExit(1)

from generate_circuit_svg import _load_telemetry, geometry_from_telemetry
from slim_replays import slim_payload  # shared numeric-precision policy (born-slim bakes)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "website" / "public" / "data"
ROUNDS_DIR = DATA_DIR / "rounds"
REPLAYS_DIR = DATA_DIR / "replays"
SEASON_JSON = DATA_DIR / "season.json"
CACHE_DIR = PROJECT_ROOT / "f1_cache"

SCHEMA_VERSION = 1
DEFAULT_DT = 1.0          # seconds of session time between frames
MAX_FRAMES = 5400         # frame budget; cadence widens past this (long/red-flag races)
COORD_DECIMALS = 1
# Track outline fills the 0..1000 viewBox; real positions (racing line, pit lane,
# run-off) sit a little outside it, but a sample hundreds of units out is a GPS
# glitch. Drop those before interpolating so the car isn't flung off-map.
VIEW_MIN = -100.0
VIEW_MAX = 1100.0

# FastF1 track-status code → broadcast label.
TRACK_STATUS_LABELS = {
    "1": "Green",
    "2": "Yellow",
    "3": "Yellow",  # unused in practice; treat as yellow
    "4": "Safety Car",
    "5": "Red Flag",
    "6": "VSC",
    "7": "VSC Ending",
}


# ── small helpers ─────────────────────────────────────────────────────────
def _sec(series: pd.Series | pd.Timedelta) -> np.ndarray | float:
    """Convert a pandas Timedelta (or a Series of them) to float seconds; NaT→nan."""
    td = pd.to_timedelta(series, errors="coerce")
    if isinstance(td, pd.Series):
        return td.dt.total_seconds().to_numpy(dtype=np.float64)
    return float(td.total_seconds()) if td is not pd.NaT and not pd.isna(td) else np.nan


def _round_or_none(value: float, decimals: int = COORD_DECIMALS) -> float | None:
    return None if not np.isfinite(value) else round(float(value), decimals)


def _resolve_round(round_num: int) -> tuple[str, int]:
    """Return (gpKey, season) for a round from season.json."""
    with SEASON_JSON.open() as f:
        season = json.load(f)
    year = int(season.get("season", 2026))
    for entry in season.get("calendar", []):
        if int(entry.get("round", -1)) == round_num:
            gp_key = entry.get("gpKey") or entry.get("name")
            if gp_key:
                return str(gp_key), year
    raise SystemExit(f"cannot resolve gpKey for round {round_num} in season.json")


def _driver_meta() -> dict[str, dict[str, Any]]:
    """code → {fullName, number, team, teamColor} from season.json (the same
    palette the website renders, so cars match the rest of the site)."""
    with SEASON_JSON.open() as f:
        season = json.load(f)
    meta: dict[str, dict[str, Any]] = {}
    for d in season.get("drivers", []):
        code = d.get("code")
        if code:
            meta[code] = {
                "fullName": d.get("fullName", code),
                "number": d.get("number"),
                "team": d.get("team", ""),
                "teamColor": d.get("teamColor", "#888888"),
            }
    return meta


def _completed_rounds() -> list[int]:
    with SEASON_JSON.open() as f:
        season = json.load(f)
    completed = season.get("completedRounds", [])
    if isinstance(completed, list):
        return [int(r) for r in completed]
    return list(range(1, int(completed) + 1))


# ── per-driver lap timeline ───────────────────────────────────────────────
def _looks_like_full_lap(tel) -> bool:
    """True if a telemetry frame traces a full 2D circuit loop, not a partial
    or near-straight fragment. Monaco's GPS dropouts leave some laps with only
    a slice of the track, which would collapse into a degenerate line — reject
    those so the outline isn't garbage."""
    if tel is None or "X" not in getattr(tel, "columns", []):
        return False
    xy = tel[["X", "Y"]].to_numpy(dtype=np.float64)
    xy = xy[np.isfinite(xy).all(axis=1)]
    if len(xy) < 200:
        return False
    centred = xy - xy.mean(axis=0)
    eig = np.linalg.eigvalsh(np.cov(centred.T))  # ascending
    if eig[-1] <= 0 or eig[0] / eig[-1] < 0.05:  # too collinear → partial trace
        return False
    # A lap returns near its start; a fragment does not.
    diag = float(np.hypot(*(xy.max(axis=0) - xy.min(axis=0))))
    return diag > 0 and np.hypot(*(xy[0] - xy[-1])) < 0.4 * diag


def _geometry_telemetry(session, season: int, gp_key: str):
    """Return (telemetry, circuit_info) for building the track outline.

    Prefer a clean full-lap trace from THIS race (so track + cars share one
    frame), scanning fastest-first and skipping partial/dropout laps. If none
    qualify (e.g. Monaco, where the whole session's position channel is patchy),
    fall back to ``generate_circuit_svg._load_telemetry``, which walks back to a
    prior season's clean layout — FastF1's per-circuit X/Y frame is stable across
    years, so the transform still lands the current race's cars on the track.
    """
    laps = session.laps
    ordered = laps.dropna(subset=["LapTime"]).sort_values("LapTime")
    tried = 0
    for _, lap in ordered.iterrows():
        if tried >= 25:
            break
        tried += 1
        try:
            tel = lap.get_telemetry()
        except Exception:  # noqa: BLE001
            continue
        if _looks_like_full_lap(tel):
            try:
                info = session.get_circuit_info()
            except Exception:  # noqa: BLE001
                info = None
            return tel, info
    # No clean lap this year — borrow the layout from a recent prior season.
    print("    no clean full-lap trace this race — falling back to prior-season layout")
    return _load_telemetry(season, gp_key)


def _compress_replay(cars, run_count, frame_codes, n_frames, dt):
    """Drop frames that carry no watchable action, returning a keep-mask-applied
    (cars, frame_codes, n_frames).

    Two cases:
      * **Lead-in** — a red-flagged / formation opening has the field strung out
        around the whole lap before it forms up on the grid. Start at the most
        bunched moment so the replay never opens with cars teleporting. (A normal
        standing start is already bunched, so nothing is trimmed.)
      * **Red-flag stoppage** — a long interior stretch where the cars are parked
        in the pit lane (almost none running) would otherwise play as minutes of
        empty track. Cut it. Safety-car periods keep the field circulating, so
        their frames survive this test and are preserved.
    """
    keep = np.ones(n_frames, dtype=bool)

    def diag(i):
        xs = [c["x"][i] for c in cars.values() if c["x"][i] is not None]
        ys = [c["y"][i] for c in cars.values() if c["y"][i] is not None]
        if len(xs) < 5:
            return 0.0
        return float(np.hypot(max(xs) - min(xs), max(ys) - min(ys)))

    window = min(n_frames, max(1, int(120 / dt)))
    spreads = [diag(i) for i in range(window)]
    if spreads and spreads[0] > 300:
        si = int(np.argmin(spreads))
        if si > 1 and spreads[si] < 0.5 * spreads[0]:
            keep[:si] = False

    dead = run_count < 4
    min_dead = max(1, int(60 / dt))
    i = 0
    while i < n_frames:
        if dead[i]:
            j = i
            while j < n_frames and dead[j]:
                j += 1
            leading = i == 0
            trailing = j == n_frames
            # Drop the ends whenever the field is absent (formation lead-in, a
            # truncated-telemetry tail), and any long interior gap (red-flag
            # stoppage). Safety-car laps keep >4 cars circulating, so survive.
            if leading or trailing or (j - i) >= min_dead:
                keep[i:j] = False
            i = j
        else:
            i += 1

    kept = int(keep.sum())
    if kept != n_frames:
        for c in cars.values():
            for k in ("x", "y", "lap", "gap"):
                c[k] = [v for v, kp in zip(c[k], keep) if kp]
        frame_codes = [fc for fc, kp in zip(frame_codes, keep) if kp]
        print(f"    compressed {n_frames - kept} lead-in/red-flag frames → {kept}")
    return cars, frame_codes, kept


def _lap_boundaries(driver_laps: pd.DataFrame, t_start: float, ref_lap: float):
    """Return (lap_numbers, starts, ends) as float arrays, filling missing
    LapStartTime (FastF1 frequently omits lap 1) from the previous lap's end."""
    dl = driver_laps.sort_values("LapNumber")
    lap_nums = dl["LapNumber"].to_numpy(dtype=np.float64)
    starts = _sec(dl["LapStartTime"])
    times = _sec(dl["LapTime"])
    starts = np.asarray(starts, dtype=np.float64).copy()
    for i in range(len(starts)):
        if not np.isfinite(starts[i]):
            if i == 0:
                starts[i] = t_start
            else:
                prev_len = times[i - 1] if np.isfinite(times[i - 1]) else ref_lap
                starts[i] = starts[i - 1] + prev_len
    ends = np.empty_like(starts)
    if len(starts) > 1:
        ends[:-1] = starts[1:]
    last_len = times[-1] if np.isfinite(times[-1]) else ref_lap
    ends[-1] = starts[-1] + last_len
    return lap_nums.astype(int), starts, ends


def build_replay(round_num: int, season: int, gp_key: str, dt: float) -> dict[str, Any]:
    print(f"  • {season} R{round_num} {gp_key}: loading FastF1 race session…")
    # Load by ROUND NUMBER, never by name: FastF1's name matching silently
    # fuzzy-matches (it has returned Austria for "Great Britain"), which would
    # bake one race's telemetry under another round. The round-number path is
    # unambiguous; we still verify the returned event's identity below.
    session = fastf1.get_session(season, round_num, "R")
    session.load(laps=True, telemetry=True, weather=False, messages=False)
    try:
        actual_round = int(session.event["RoundNumber"])
    except Exception:  # noqa: BLE001
        actual_round = None
    if actual_round is not None and actual_round != round_num:
        raise SystemExit(
            f"wrong-event guard: FastF1 returned round {actual_round}, expected {round_num} "
            f"({gp_key}) — refusing to bake mismatched telemetry"
        )

    laps = session.laps
    if laps is None or len(laps) == 0:
        raise SystemExit("no laps in session — cannot build replay")

    # ── geometry + shared transform (identical to circuitInfo.geometry) ──
    geo_tel = _geometry_telemetry(session, season, gp_key)
    if geo_tel is None:
        raise SystemExit("no lap yielded usable position telemetry for the track outline")
    tel, info = geo_tel
    geo_result = geometry_from_telemetry(tel, info)
    if geo_result is None:
        raise SystemExit("could not build circuit geometry from telemetry")
    geometry, transform = geo_result

    # ── race window on the session clock ──
    all_starts = _sec(laps["LapStartTime"])
    all_times = _sec(laps["LapTime"])
    lap1_starts = _sec(laps.loc[laps["LapNumber"] == 1, "LapStartTime"])
    t_start = np.nanmin(lap1_starts) if np.any(np.isfinite(lap1_starts)) else np.nanmin(all_starts)
    lap_ends = all_starts + all_times
    t_end = np.nanmax(lap_ends)
    if not np.isfinite(t_start) or not np.isfinite(t_end) or t_end <= t_start:
        raise SystemExit("degenerate race window")

    # Reference lap time (median green-flag lap) → gap-to-leader in seconds.
    green = _sec(laps.loc[laps["TrackStatus"].astype(str) == "1", "LapTime"])
    green = green[np.isfinite(green)]
    ref_lap = float(np.median(green)) if len(green) else float(np.nanmedian(all_times))
    if not np.isfinite(ref_lap) or ref_lap <= 0:
        ref_lap = 90.0

    # Adaptive cadence: keep normal races at the requested dt (1 s), but bound
    # the frame budget so a red-flagged / suspended race (Monaco 2026 ran ~2h23m
    # with a stoppage) doesn't balloon the file. The client interpolates between
    # frames, so a slightly coarser dt stays visually smooth.
    duration_raw = t_end - t_start
    dt_eff = dt
    if duration_raw / dt_eff > MAX_FRAMES:
        dt_eff = max(dt, float(np.ceil((duration_raw / MAX_FRAMES) * 2) / 2))
        print(f"    long race — cadence widened to {dt_eff}s to cap frames")
    dt = dt_eff

    grid_t = np.arange(t_start, t_end + dt, dt, dtype=np.float64)
    n_frames = len(grid_t)
    total_laps = int(np.nanmax(laps["LapNumber"].to_numpy()))
    print(
        f"    window {t_end - t_start:.0f}s · {n_frames} frames @ {dt}s · "
        f"{total_laps} laps · ref-lap {ref_lap:.1f}s"
    )

    meta = _driver_meta()
    results = session.results

    drivers_out: list[dict[str, Any]] = []
    cars: dict[str, dict[str, Any]] = {}
    stints_out: dict[str, list[dict[str, Any]]] = {}
    # Progress + running mask matrices for the order/gap pass.
    prog = np.full((len(results), n_frames), -np.inf, dtype=np.float64)
    running = np.zeros((len(results), n_frames), dtype=bool)
    codes: list[str] = []

    for di, (_, res) in enumerate(results.iterrows()):
        code = res["Abbreviation"]
        num = str(res["DriverNumber"])
        dl = laps[laps["Driver"] == code]
        if len(dl) == 0:
            continue
        m = meta.get(code, {})
        team = m.get("team") or res.get("TeamName") or ""
        color = m.get("teamColor") or (f"#{res['TeamColor']}" if res.get("TeamColor") else "#888888")
        grid = res.get("GridPosition")
        drivers_out.append(
            {
                "code": code,
                "number": int(m.get("number") or (int(num) if num.isdigit() else 0)),
                "name": m.get("fullName") or res.get("FullName") or code,
                "team": team,
                "teamColor": color,
                "grid": int(grid) if grid and np.isfinite(grid) and grid > 0 else None,
            }
        )
        codes.append(code)

        lap_nums, starts, ends = _lap_boundaries(dl, t_start, ref_lap)
        driver_end = float(ends[-1])

        # current-lap index per frame
        idx = np.clip(np.searchsorted(starts, grid_t, side="right") - 1, 0, len(starts) - 1)
        seg_start = starts[idx]
        seg_end = ends[idx]
        frac_time = np.clip((grid_t - seg_start) / np.maximum(seg_end - seg_start, 1e-6), 0.0, 1.0)
        lap_of_frame = lap_nums[idx]
        p = (lap_of_frame - 1) + frac_time

        # true positions from pos_data → viewBox space. Project the raw samples
        # first, drop out-of-viewBox GPS glitches, THEN interpolate onto the
        # frame grid — so a bad sample is bridged over, not teleported to.
        pdd = session.pos_data.get(num)
        xv = np.full(n_frames, np.nan)
        yv = np.full(n_frames, np.nan)
        if pdd is not None and len(pdd):
            st = _sec(pdd["SessionTime"])
            fx = pdd["X"].to_numpy(dtype=np.float64)
            fy = pdd["Y"].to_numpy(dtype=np.float64)
            ok = np.isfinite(st) & np.isfinite(fx) & np.isfinite(fy)
            if ok.sum() >= 2:
                prj = transform.apply(np.column_stack([fx[ok], fy[ok]]))
                good = (
                    (prj[:, 0] > VIEW_MIN) & (prj[:, 0] < VIEW_MAX)
                    & (prj[:, 1] > VIEW_MIN) & (prj[:, 1] < VIEW_MAX)
                )
                sts = st[ok][good]
                if len(sts) >= 2:
                    order = np.argsort(sts)
                    sts_o = sts[order]
                    xv = np.interp(grid_t, sts_o, prj[good, 0][order], left=np.nan, right=np.nan)
                    yv = np.interp(grid_t, sts_o, prj[good, 1][order], left=np.nan, right=np.nan)

        # running window: after the race start, up to the driver's last lap end.
        on = (grid_t >= t_start - 1e-6) & (grid_t <= driver_end + dt) & np.isfinite(xv) & np.isfinite(yv)
        running[di] = on
        prog[di] = np.where(on, p, -np.inf)

        cars[code] = {
            "x": [_round_or_none(v) for v in np.where(on, xv, np.nan)],
            "y": [_round_or_none(v) for v in np.where(on, yv, np.nan)],
            "lap": [int(v) for v in np.clip(lap_of_frame, 1, total_laps)],
            # gap filled in the order pass below
            "gap": None,
        }

        # tyre stints
        stints: list[dict[str, Any]] = []
        for stint_id, g in dl.groupby("Stint"):
            comp_series = g["Compound"].dropna()
            compound = str(comp_series.iloc[0]) if len(comp_series) else "UNKNOWN"
            stints.append(
                {
                    "compound": compound,
                    "startLap": int(g["LapNumber"].min()),
                    "endLap": int(g["LapNumber"].max()),
                }
            )
        stints_out[code] = sorted(stints, key=lambda s: s["startLap"])

    # ── order / gap-to-leader per frame ──
    leader_p = prog.max(axis=0)  # -inf only if nobody running (shouldn't happen)
    for di, code in enumerate(codes):
        deficit = leader_p - prog[di]
        gap_s = deficit * ref_lap
        on = running[di]
        cars[code]["gap"] = [
            (0.0 if d <= 0 else round(float(g), 1)) if o else None
            for o, d, g in zip(on, deficit, gap_s)
        ]

    # ── per-frame track-status code (green/yellow/SC/VSC/red) ──
    # Sampled onto the frame grid so it survives frame compression below; the
    # segment timeline is derived afterwards, in the compressed frame clock.
    frame_codes = ["1"] * n_frames
    ts = session.track_status
    if ts is not None and len(ts):
        ts_sec = _sec(ts["Time"])
        finite = np.isfinite(ts_sec)
        tsec = ts_sec[finite]
        tcodes = np.asarray([str(c) for c in ts["Status"].to_numpy()])[finite]
        if len(tsec):
            order = np.argsort(tsec)
            tsec, tcodes = tsec[order], tcodes[order]
            idx = np.searchsorted(tsec, grid_t, side="right") - 1
            frame_codes = [tcodes[k] if k >= 0 else tcodes[0] for k in idx]

    # Drop lead-in + red-flag-parked dead frames (no-op for a clean race).
    run_count = running.sum(axis=0)
    cars, frame_codes, n_frames = _compress_replay(cars, run_count, frame_codes, n_frames, dt)

    # Derive the flag timeline from the (compressed) per-frame codes.
    track_status: list[dict[str, Any]] = []
    prev_code = None
    for f, code in enumerate(frame_codes):
        if code != prev_code:
            prev_code = code
            track_status.append(
                {"t": round(f * dt, 1), "code": code, "label": TRACK_STATUS_LABELS.get(code, code)}
            )

    # ── final classification ──
    finish: list[dict[str, Any]] = []
    res_sorted = results.sort_values("Position", na_position="last")
    for _, res in res_sorted.iterrows():
        pos = res.get("Position")
        if not (pos and np.isfinite(pos)):
            continue
        status = str(res.get("Status", ""))
        gap_time = _sec(res.get("Time"))
        gap_val = 0.0 if int(pos) == 1 else (round(float(gap_time), 3) if (status == "Finished" and np.isfinite(gap_time)) else None)
        finish.append(
            {
                "code": res["Abbreviation"],
                "position": int(pos),
                "laps": int(res.get("Laps")) if res.get("Laps") and np.isfinite(res.get("Laps")) else total_laps,
                "status": status,
                "gap": gap_val,
                "points": float(res.get("Points") or 0.0),
            }
        )

    with SEASON_JSON.open() as f:
        season_json = json.load(f)
    cal = {int(e.get("round", -1)): e for e in season_json.get("calendar", [])}
    entry = cal.get(round_num, {})

    return {
        "schemaVersion": SCHEMA_VERSION,
        "sport": "f1",
        "season": season,
        "round": round_num,
        "name": entry.get("name") or gp_key,
        "gpKey": entry.get("gpKey") or gp_key,
        "circuit": entry.get("circuit") or "",
        "source": "fastf1",
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "totalLaps": total_laps,
        "dt": dt,
        "frameCount": n_frames,
        "duration": round((n_frames - 1) * dt, 1),
        "geometry": geometry,
        "drivers": sorted(drivers_out, key=lambda d: (d["grid"] is None, d["grid"] or 99)),
        "cars": cars,
        "stints": stints_out,
        "trackStatus": track_status,
        "drsZones": [],
        "finish": finish,
    }


def _write(round_num: int, payload: dict[str, Any]) -> None:
    REPLAYS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPLAYS_DIR / f"round_{round_num:02d}.json"
    # Reduce numeric precision (drop redundant `.0`, cap over-precise scalars) so
    # freshly baked replays are born as slim as src/slim_replays.py makes the
    # committed ones — same policy, no schema change.
    slim_payload(payload)
    with out.open("w") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")
    size_kb = out.stat().st_size / 1024
    print(f"  ✅ round {round_num}: {out.name}  ({size_kb:.0f} KB, {payload['frameCount']} frames)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--round", type=int, help="Bake a single round")
    group.add_argument("--all-completed", action="store_true", help="Bake every completed round")
    parser.add_argument("--season", type=int, default=None, help="Override season year")
    parser.add_argument("--dt", type=float, default=DEFAULT_DT, help="Seconds between frames")
    args = parser.parse_args(argv)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    rounds = [args.round] if args.round else _completed_rounds()
    for rnd in rounds:
        gp_key, season = _resolve_round(rnd)
        if args.season is not None:
            season = args.season
        try:
            payload = build_replay(rnd, season, gp_key, args.dt)
            _write(rnd, payload)
        except SystemExit as exc:
            print(f"  ⚠ round {rnd}: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ round {rnd}: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
