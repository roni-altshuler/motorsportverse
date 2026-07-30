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

from generate_circuit_svg import geometry_from_telemetry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "website" / "public" / "data"
ROUNDS_DIR = DATA_DIR / "rounds"
REPLAYS_DIR = DATA_DIR / "replays"
SEASON_JSON = DATA_DIR / "season.json"
CACHE_DIR = PROJECT_ROOT / "f1_cache"

SCHEMA_VERSION = 1
DEFAULT_DT = 1.0          # seconds of session time between frames
COORD_DECIMALS = 1

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
    session = fastf1.get_session(season, gp_key, "R")
    session.load(laps=True, telemetry=True, weather=False, messages=False)

    laps = session.laps
    if laps is None or len(laps) == 0:
        raise SystemExit("no laps in session — cannot build replay")

    # ── geometry + shared transform (identical to circuitInfo.geometry) ──
    fastest = session.laps.pick_fastest()
    tel = fastest.get_telemetry()
    info = session.get_circuit_info()
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

        # true positions from pos_data → viewBox space
        pdd = session.pos_data.get(num)
        xg = np.full(n_frames, np.nan)
        yg = np.full(n_frames, np.nan)
        if pdd is not None and len(pdd):
            st = _sec(pdd["SessionTime"])
            fx = pdd["X"].to_numpy(dtype=np.float64)
            fy = pdd["Y"].to_numpy(dtype=np.float64)
            ok = np.isfinite(st) & np.isfinite(fx) & np.isfinite(fy)
            if ok.sum() >= 2:
                order = np.argsort(st[ok])
                sts = st[ok][order]
                xg = np.interp(grid_t, sts, fx[ok][order], left=np.nan, right=np.nan)
                yg = np.interp(grid_t, sts, fy[ok][order], left=np.nan, right=np.nan)
        proj = transform.apply(np.column_stack([xg, yg]))
        xv, yv = proj[:, 0], proj[:, 1]

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

    # ── track-status timeline (relative to race start) ──
    # Collapse the pre-race formation-lap flag flicker into a single initial
    # state (the status active at lights-out), then emit real changes only.
    track_status: list[dict[str, Any]] = []
    ts = session.track_status
    if ts is not None and len(ts):
        ts_sec = _sec(ts["Time"])
        initial = None  # (code, message) active at t_start
        changes: list[tuple[float, str, str]] = []
        for tsec, row in zip(ts_sec, ts.itertuples(index=False)):
            if not np.isfinite(tsec):
                continue
            code = str(getattr(row, "Status"))
            msg = str(getattr(row, "Message", code))
            if tsec <= t_start + 1e-9:
                initial = (code, msg)
            else:
                changes.append((float(tsec - t_start), code, msg))
        if initial is None:
            initial = ("1", "Green")  # race began before any recorded status
        prev_code = initial[0]
        track_status.append(
            {"t": 0.0, "code": prev_code, "label": TRACK_STATUS_LABELS.get(prev_code, initial[1])}
        )
        for tt, code, msg in changes:
            if code == prev_code:
                continue
            prev_code = code
            track_status.append(
                {"t": round(tt, 1), "code": code, "label": TRACK_STATUS_LABELS.get(code, msg)}
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
        "duration": round(float(grid_t[-1] - grid_t[0]), 1),
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
