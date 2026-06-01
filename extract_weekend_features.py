"""Extract pre-race weekend features from the FastF1 cache.

Reads cached FastF1 sessions (FP2 + Qualifying) for every 2024–2025 round
and writes a per-driver-per-round feature parquet:

* ``fp2_longrun_pace_norm`` — median long-run lap time (TyreLife ≥ 4)
  divided by the session's fastest such median. 1.0 = pole-pace; >1 = slower.
* ``fp2_longrun_consistency`` — std of long-run lap times in seconds.
* ``q_sector_dominance_norm`` — sum of driver's best (S1+S2+S3) divided by
  the session's fastest ideal lap.
* ``q_top_speed_norm`` — driver's max trap speed in Q divided by the
  session's overall max.
* ``race_track_temp`` — track temperature near race start (Q snapshot).
* ``race_air_temp`` — air temperature, same.
* ``race_rainfall`` — 1.0 if Q rainfall flag was true, else 0.0.

All of these are KNOWN at pre-race time and therefore leak-safe with
respect to race outcomes.

Output: ``data/weekend_features.parquet``
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Silence FastF1 chatter unless explicitly enabled with --verbose.
warnings.filterwarnings("ignore")
logging.getLogger("fastf1").setLevel(logging.WARNING)
for noisy in ("core", "req", "_api"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

import fastf1  # noqa: E402  (after logging silenced)

PROJECT_ROOT = Path(__file__).resolve().parent
F1_CACHE_DIR = PROJECT_ROOT / "f1_cache"
OUTPUT_PATH = PROJECT_ROOT / "data" / "weekend_features.parquet"


@dataclass
class WeekendRow:
    season: int
    round: int
    driver: str
    fp2_longrun_pace_norm: float
    fp2_longrun_consistency: float
    q_sector_dominance_norm: float
    q_top_speed_norm: float
    race_track_temp: float
    race_air_temp: float
    race_rainfall: float
    # Phase 8 — dynamic weekend evolution features
    fp2_deg_slope: float          # seconds-per-lap tire degradation slope
    q_vs_fp2_pace_delta: float    # (Q best - FP2 best) / FP2 best — relative
    intra_stint_drift: float      # late-half-median - early-half-median (s)


def _enable_cache() -> None:
    F1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(F1_CACHE_DIR))


def _safe_load(year: int, round_: int, session_name: str):
    """Load a session; return None if it's missing or won't load."""
    try:
        session = fastf1.get_session(year, round_, session_name)
        session.load(laps=True, telemetry=False, weather=True, messages=False)
        return session
    except Exception:
        return None


def _fp2_longrun_features(session) -> dict[str, dict[str, float]]:
    """Per-driver FP2 long-run pace + Phase-8 dynamic curves.

    Long-run definition: TyreLife >= 4 (the driver has done at least 4
    laps on the current set, so the lap is part of a representative
    stint rather than an out-lap on fresh tyres).

    Returns ``{driver: {"median_s": float, "std_s": float, "best_s": float,
    "deg_slope": float, "intra_stint_drift": float}}``.

    Phase-8 dynamic columns:

    * ``deg_slope`` — linear regression slope of LapTimeSec vs LapNumber
      within each stint, averaged across stints. Units: seconds-per-lap.
      Positive = pace falls off as tyres wear; ~0 = stable; negative = improving.
    * ``intra_stint_drift`` — late-half-median minus early-half-median of
      LapTimeSec within each long-run stint (≥6 laps). Averaged across
      stints. Captures fine-grained intra-stint pace degradation.
    """
    out: dict[str, dict[str, float]] = {}
    if session is None or session.laps.empty:
        return out
    laps = session.laps
    if "TyreLife" not in laps.columns or "LapTime" not in laps.columns:
        return out
    longrun = laps[(laps["TyreLife"] >= 4) & laps["LapTime"].notna()].copy()
    if longrun.empty:
        return out
    longrun["LapTimeSec"] = longrun["LapTime"].dt.total_seconds()

    # Also pull best lap across the WHOLE FP2 session (not just long-run) for
    # the Phase-8 Q-vs-FP2 delta feature.
    fp2_all = laps[laps["LapTime"].notna()].copy()
    fp2_all["LapTimeSec"] = fp2_all["LapTime"].dt.total_seconds()
    best_by_driver = fp2_all.groupby("Driver")["LapTimeSec"].min().to_dict()

    for drv, grp in longrun.groupby("Driver"):
        if len(grp) < 3:
            continue
        median_s = float(grp["LapTimeSec"].median())
        std_s = float(grp["LapTimeSec"].std())

        # Degradation slope + intra-stint drift per stint, then average.
        slopes: list[float] = []
        drifts: list[float] = []
        if "Stint" in grp.columns:
            for _stint, stint_grp in grp.groupby("Stint"):
                if len(stint_grp) < 3 or "LapNumber" not in stint_grp.columns:
                    continue
                x = stint_grp["LapNumber"].to_numpy(dtype=float)
                y = stint_grp["LapTimeSec"].to_numpy(dtype=float)
                # Linear slope; np.polyfit deg=1 returns (slope, intercept).
                try:
                    slope = float(np.polyfit(x, y, deg=1)[0])
                    if np.isfinite(slope):
                        slopes.append(slope)
                except Exception:
                    pass
                # Intra-stint drift on stints with at least 6 laps.
                if len(stint_grp) >= 6:
                    sorted_g = stint_grp.sort_values("LapNumber")
                    half = len(sorted_g) // 2
                    early = sorted_g.iloc[:half]["LapTimeSec"].median()
                    late = sorted_g.iloc[half:]["LapTimeSec"].median()
                    drift = float(late - early)
                    if np.isfinite(drift):
                        drifts.append(drift)
        deg_slope = float(np.mean(slopes)) if slopes else float("nan")
        intra_drift = float(np.mean(drifts)) if drifts else float("nan")

        out[str(drv)] = {
            "median_s": median_s,
            "std_s": std_s,
            "best_s": float(best_by_driver.get(drv, float("nan"))),
            "deg_slope": deg_slope,
            "intra_stint_drift": intra_drift,
        }
    return out


def _q_sector_features(session) -> dict[str, dict[str, float]]:
    """Per-driver Q best-sector dominance + top trap speed.

    Best-sector sum: per driver, take the minimum of each sector (S1, S2,
    S3) across all their Q laps and sum — i.e., the *ideal* lap.

    Top speed: max of SpeedI1 / SpeedI2 / SpeedST / SpeedFL across laps.
    """
    out: dict[str, dict[str, float]] = {}
    if session is None or session.laps.empty:
        return out
    laps = session.laps
    sec_cols = ("Sector1Time", "Sector2Time", "Sector3Time")
    if not all(c in laps.columns for c in sec_cols):
        return out
    speed_cols = [c for c in ("SpeedI1", "SpeedI2", "SpeedST", "SpeedFL") if c in laps.columns]
    # Also pull best Q lap per driver for the Phase-8 Q-vs-FP2 delta.
    laps_with_time = laps[laps["LapTime"].notna()].copy()
    if not laps_with_time.empty:
        laps_with_time["LapTimeSec"] = laps_with_time["LapTime"].dt.total_seconds()
        q_best_by_driver = laps_with_time.groupby("Driver")["LapTimeSec"].min().to_dict()
    else:
        q_best_by_driver = {}
    for drv, grp in laps.groupby("Driver"):
        sec_secs: list[float] = []
        ok = True
        for col in sec_cols:
            non_null = grp[col].dropna()
            if non_null.empty:
                ok = False
                break
            sec_secs.append(float(non_null.dt.total_seconds().min()))
        if not ok:
            continue
        top_speed = 0.0
        if speed_cols:
            stacked = grp[speed_cols].values.astype(float).ravel()
            valid = stacked[np.isfinite(stacked) & (stacked > 0)]
            if valid.size:
                top_speed = float(valid.max())
        out[str(drv)] = {
            "ideal_lap_s": float(sum(sec_secs)),
            "top_speed_kph": top_speed,
            "q_best_lap_s": float(q_best_by_driver.get(drv, float("nan"))),
        }
    return out


def _q_weather_snapshot(session) -> dict[str, float]:
    """Track temp / air temp / rainfall at Q (proxy for pre-race conditions)."""
    if session is None or session.weather_data is None or session.weather_data.empty:
        return {"track_temp": float("nan"), "air_temp": float("nan"), "rainfall": 0.0}
    w = session.weather_data
    return {
        "track_temp": float(w["TrackTemp"].median()) if "TrackTemp" in w.columns else float("nan"),
        "air_temp": float(w["AirTemp"].median()) if "AirTemp" in w.columns else float("nan"),
        "rainfall": float(bool(w["Rainfall"].any())) if "Rainfall" in w.columns else 0.0,
    }


def _normalise_for_round(rows: list[WeekendRow]) -> list[WeekendRow]:
    """Normalise FP2 pace and Q ideal-lap into per-session ratios."""
    if not rows:
        return rows
    fp2_meds = [r.fp2_longrun_pace_norm for r in rows if r.fp2_longrun_pace_norm > 0]
    q_ideals = [r.q_sector_dominance_norm for r in rows if r.q_sector_dominance_norm > 0]
    top_speeds = [r.q_top_speed_norm for r in rows if r.q_top_speed_norm > 0]
    if fp2_meds:
        fastest = min(fp2_meds)
        for r in rows:
            if r.fp2_longrun_pace_norm > 0:
                r.fp2_longrun_pace_norm = r.fp2_longrun_pace_norm / fastest
            else:
                r.fp2_longrun_pace_norm = float("nan")
    if q_ideals:
        fastest = min(q_ideals)
        for r in rows:
            if r.q_sector_dominance_norm > 0:
                r.q_sector_dominance_norm = r.q_sector_dominance_norm / fastest
            else:
                r.q_sector_dominance_norm = float("nan")
    if top_speeds:
        fastest = max(top_speeds)
        for r in rows:
            if r.q_top_speed_norm > 0:
                r.q_top_speed_norm = r.q_top_speed_norm / fastest
            else:
                r.q_top_speed_norm = float("nan")
    return rows


def extract_round(year: int, round_: int) -> list[WeekendRow]:
    """Extract per-driver weekend features for one round."""
    fp2 = _safe_load(year, round_, "FP2")
    q = _safe_load(year, round_, "Q")
    fp2_feats = _fp2_longrun_features(fp2)
    q_feats = _q_sector_features(q)
    weather = _q_weather_snapshot(q)

    drivers = set(fp2_feats) | set(q_feats)
    if not drivers:
        return []
    rows: list[WeekendRow] = []
    for drv in sorted(drivers):
        fp2_d = fp2_feats.get(drv, {})
        q_d = q_feats.get(drv, {})
        # Q-vs-FP2 best-lap delta (relative): (Q_best - FP2_best) / FP2_best.
        # Negative = Q faster than FP2 (typical, after Q dialed up); positive
        # means driver couldn't reproduce their FP2 single-lap pace in Q.
        fp2_best = fp2_d.get("best_s")
        q_best = q_d.get("q_best_lap_s")
        if (
            fp2_best is not None
            and q_best is not None
            and isinstance(fp2_best, (int, float))
            and isinstance(q_best, (int, float))
            and fp2_best > 0
            and np.isfinite(fp2_best)
            and np.isfinite(q_best)
        ):
            q_vs_fp2 = float((q_best - fp2_best) / fp2_best)
        else:
            q_vs_fp2 = float("nan")
        rows.append(
            WeekendRow(
                season=year,
                round=round_,
                driver=str(drv),
                fp2_longrun_pace_norm=float(fp2_d.get("median_s", 0.0)),
                fp2_longrun_consistency=float(fp2_d.get("std_s", float("nan"))),
                q_sector_dominance_norm=float(q_d.get("ideal_lap_s", 0.0)),
                q_top_speed_norm=float(q_d.get("top_speed_kph", 0.0)),
                race_track_temp=weather["track_temp"],
                race_air_temp=weather["air_temp"],
                race_rainfall=weather["rainfall"],
                fp2_deg_slope=float(fp2_d.get("deg_slope", float("nan"))),
                q_vs_fp2_pace_delta=q_vs_fp2,
                intra_stint_drift=float(fp2_d.get("intra_stint_drift", float("nan"))),
            )
        )
    rows = _normalise_for_round(rows)
    return rows


def extract_seasons(seasons: list[int], rounds: int = 24) -> pd.DataFrame:
    all_rows: list[WeekendRow] = []
    for year in seasons:
        for r in range(1, rounds + 1):
            rows = extract_round(year, r)
            if not rows:
                print(f"  [{year} R{r:02d}] no usable weekend data — skipped")
                continue
            all_rows.extend(rows)
            print(f"  [{year} R{r:02d}] extracted {len(rows)} drivers")
    df = pd.DataFrame([r.__dict__ for r in all_rows])
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025])
    parser.add_argument("--rounds", type=int, default=24)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    _enable_cache()
    df = extract_seasons(args.seasons, args.rounds)
    if df.empty:
        print("no rows extracted — check the FastF1 cache contents")
        return 1
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    print(f"\nwrote {len(df)} rows ({df['driver'].nunique()} drivers, "
          f"{df.groupby(['season','round']).ngroups} rounds) to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
