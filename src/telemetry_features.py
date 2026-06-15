#!/usr/bin/env python3
"""
telemetry_features.py
=====================
Extract telemetry-based features from FastF1:
  - Speed trap data (max speeds per sector per driver)
  - Sector times (best S1/S2/S3 and ideal lap times)

These are exported as JSON fields inside each round file
for the website to display.

Usage:
    python telemetry_features.py --round 1 --year <season-year>
    python telemetry_features.py --all --year <season-year>
"""

import argparse
import json
import os
import sys
import warnings


warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))
from f1_prediction_utils import (
    CALENDAR,
    TEAM_COLOURS,
    DRIVER_TEAM,
    SEASON_YEAR,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_ROUNDS_DIR = os.path.join(PROJECT_ROOT, "website", "public", "data", "rounds")
F1_CACHE_DIR = os.path.join(PROJECT_ROOT, "f1_cache")

try:
    import fastf1
except ImportError:
    print("⚠️  FastF1 not installed. Install with: pip install fastf1")
    sys.exit(1)


def enable_cache():
    os.makedirs(F1_CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(F1_CACHE_DIR)


# ═══════════════════════════════════════════════════════════════════════════
# Speed Trap Extraction
# ═══════════════════════════════════════════════════════════════════════════

def extract_speed_traps(year: int, gp_key: str, session_type: str = "Q") -> list[dict]:
    """
    Extract max speed per driver per sector from telemetry data.

    Returns list of SpeedTrapEntry dicts sorted by speed descending:
      { driver, team, teamColor, speedKmh, sector }
    """
    print(f"  ⚡ Speed traps: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    speed_traps = []
    drivers = session.laps["Driver"].unique()

    for driver in drivers:
        if driver not in DRIVER_TEAM:
            continue
        driver_laps = session.laps.pick_drivers(driver)
        fastest = driver_laps.pick_fastest()
        if fastest is None or fastest.empty if hasattr(fastest, 'empty') else fastest is None:
            continue

        try:
            tel = fastest.get_telemetry()
            if tel is None or tel.empty:
                continue
        except Exception:
            continue

        team = DRIVER_TEAM.get(driver, "Unknown")
        team_color = TEAM_COLOURS.get(team, "#888888")

        # Divide telemetry into approximate thirds for sectors
        n = len(tel)
        sector_boundaries = [0, n // 3, 2 * n // 3, n]

        for s_idx in range(3):
            start = sector_boundaries[s_idx]
            end = sector_boundaries[s_idx + 1]
            sector_tel = tel.iloc[start:end]

            if len(sector_tel) > 0:
                max_speed = float(sector_tel["Speed"].max())
                speed_traps.append({
                    "driver": driver,
                    "team": team,
                    "teamColor": team_color,
                    "speedKmh": round(max_speed, 1),
                    "sector": s_idx + 1,
                })

    # Sort by speed descending
    speed_traps.sort(key=lambda x: x["speedKmh"], reverse=True)
    return speed_traps


# ═══════════════════════════════════════════════════════════════════════════
# Sector Times Extraction
# ═══════════════════════════════════════════════════════════════════════════

def extract_sector_times(year: int, gp_key: str, session_type: str = "Q") -> list[dict]:
    """
    Extract best sector times for each driver and compute ideal lap.

    Returns list of SectorTimeEntry dicts sorted by ideal lap ascending:
      { driver, team, teamColor, sector1, sector2, sector3, idealLap }
    """
    print(f"  ⏱️  Sector times: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    sector_times = []
    drivers = session.laps["Driver"].unique()

    for driver in drivers:
        if driver not in DRIVER_TEAM:
            continue
        driver_laps = session.laps.pick_drivers(driver)

        # Get best sector times across all laps
        s1_times = driver_laps["Sector1Time"].dropna()
        s2_times = driver_laps["Sector2Time"].dropna()
        s3_times = driver_laps["Sector3Time"].dropna()

        if s1_times.empty or s2_times.empty or s3_times.empty:
            continue

        # Convert timedelta to seconds
        best_s1 = s1_times.min().total_seconds()
        best_s2 = s2_times.min().total_seconds()
        best_s3 = s3_times.min().total_seconds()
        ideal_lap = best_s1 + best_s2 + best_s3

        team = DRIVER_TEAM.get(driver, "Unknown")
        team_color = TEAM_COLOURS.get(team, "#888888")

        sector_times.append({
            "driver": driver,
            "team": team,
            "teamColor": team_color,
            "sector1": round(best_s1, 3),
            "sector2": round(best_s2, 3),
            "sector3": round(best_s3, 3),
            "idealLap": round(ideal_lap, 3),
        })

    # Sort by ideal lap ascending
    sector_times.sort(key=lambda x: x["idealLap"])
    return sector_times


# ═══════════════════════════════════════════════════════════════════════════
# Race Session Insights (FastF1 meaningful additions)
# ═══════════════════════════════════════════════════════════════════════════

def extract_stint_timeline(year: int, gp_key: str, session_type: str = "R") -> list[dict]:
    """Extract stint timeline per driver.

    Returns:
      [{driver, team, teamColor, stints:[{stint, compound, startLap, endLap, laps}]}]
    """
    print(f"  🧪 Stints: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    laps = session.laps
    if laps is None or laps.empty:
        return []

    output = []
    for driver in laps["Driver"].dropna().unique():
        if driver not in DRIVER_TEAM:
            continue
        dl = laps.pick_drivers(driver)
        if dl is None or dl.empty:
            continue

        stints = []
        for stint_id, chunk in dl.groupby("Stint"):
            if chunk.empty:
                continue
            start_lap = int(chunk["LapNumber"].min())
            end_lap = int(chunk["LapNumber"].max())
            compound = str(chunk["Compound"].dropna().iloc[0]) if chunk["Compound"].dropna().size else "Unknown"
            stints.append({
                "stint": int(stint_id) if stint_id == stint_id else 0,
                "compound": compound,
                "startLap": start_lap,
                "endLap": end_lap,
                "laps": max(0, end_lap - start_lap + 1),
            })

        if stints:
            team = DRIVER_TEAM.get(driver, "Unknown")
            output.append({
                "driver": driver,
                "team": team,
                "teamColor": TEAM_COLOURS.get(team, "#888888"),
                "stints": stints,
            })

    return output


def extract_track_status_events(year: int, gp_key: str, session_type: str = "R") -> list[dict]:
    """Extract safety car / VSC related track status events.

    Returns:
      [{time, statusCode, statusLabel, message}]
    """
    print(f"  🚩 Track status: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=True)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    status_df = getattr(session, "track_status", None)
    if status_df is None or status_df.empty:
        return []

    code_map = {
        "1": "Green",
        "2": "Yellow",
        "4": "Safety Car",
        "5": "Red Flag",
        "6": "VSC",
        "7": "VSC Ending",
    }

    events = []
    for _, row in status_df.iterrows():
        code = str(row.get("Status", ""))
        if code not in {"4", "6", "7", "5", "2"}:
            continue
        t = row.get("Time", None)
        events.append({
            "time": str(t) if t is not None else "",
            "statusCode": code,
            "statusLabel": code_map.get(code, "Status"),
            "message": code_map.get(code, "Status"),
        })

    return events


def extract_pit_stop_impact(year: int, gp_key: str, session_type: str = "R") -> list[dict]:
    """Estimate pit stop impact using out-lap vs previous lap deltas.

    Returns:
      [{driver, team, teamColor, lap, pitTimeLoss, outlapDelta}]
    """
    print(f"  🔧 Pit stop impact: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    laps = session.laps
    if laps is None or laps.empty:
        return []

    output = []
    for driver in laps["Driver"].dropna().unique():
        if driver not in DRIVER_TEAM:
            continue
        dl = laps.pick_drivers(driver).sort_values("LapNumber")
        if dl.empty:
            continue

        team = DRIVER_TEAM.get(driver, "Unknown")
        team_color = TEAM_COLOURS.get(team, "#888888")

        for i in range(1, len(dl)):
            cur = dl.iloc[i]
            prev = dl.iloc[i - 1]

            pit_out = cur.get("PitOutTime", None)
            if pit_out is None or pit_out != pit_out:
                continue

            cur_lap = cur.get("LapTime", None)
            prev_lap = prev.get("LapTime", None)
            if cur_lap is None or prev_lap is None:
                continue

            try:
                outlap_delta = float(cur_lap.total_seconds() - prev_lap.total_seconds())
            except Exception:
                continue

            pit_in = cur.get("PitInTime", None)
            pit_time_loss = None
            try:
                if pit_in is not None and pit_in == pit_in:
                    pit_time_loss = float((pit_out - pit_in).total_seconds())
            except Exception:
                pit_time_loss = None

            output.append({
                "driver": driver,
                "team": team,
                "teamColor": team_color,
                "lap": int(cur.get("LapNumber", 0) or 0),
                "pitTimeLoss": round(pit_time_loss, 3) if pit_time_loss is not None else None,
                "outlapDelta": round(outlap_delta, 3),
            })

    output.sort(key=lambda x: x["lap"])
    return output


def extract_sector_dominance(year: int, gp_key: str, session_type: str = "R") -> list[dict]:
    """Compute sector rank heatmap data from each driver's best sectors.

    Returns:
      [{driver, team, teamColor, sector1Rank, sector2Rank, sector3Rank, overallRank}]
    """
    print(f"  📈 Sector dominance: {year} {gp_key} ({session_type})")
    sector_rows = extract_sector_times(year, gp_key, session_type)
    if not sector_rows:
        return []

    s1_sorted = sorted(sector_rows, key=lambda x: x["sector1"])
    s2_sorted = sorted(sector_rows, key=lambda x: x["sector2"])
    s3_sorted = sorted(sector_rows, key=lambda x: x["sector3"])
    ideal_sorted = sorted(sector_rows, key=lambda x: x["idealLap"])

    s1_rank = {r["driver"]: i + 1 for i, r in enumerate(s1_sorted)}
    s2_rank = {r["driver"]: i + 1 for i, r in enumerate(s2_sorted)}
    s3_rank = {r["driver"]: i + 1 for i, r in enumerate(s3_sorted)}
    ov_rank = {r["driver"]: i + 1 for i, r in enumerate(ideal_sorted)}

    out = []
    for r in sector_rows:
        drv = r["driver"]
        out.append({
            "driver": drv,
            "team": r["team"],
            "teamColor": r["teamColor"],
            "sector1Rank": s1_rank.get(drv, 99),
            "sector2Rank": s2_rank.get(drv, 99),
            "sector3Rank": s3_rank.get(drv, 99),
            "overallRank": ov_rank.get(drv, 99),
        })

    out.sort(key=lambda x: x["overallRank"])
    return out


def extract_race_control_events(year: int, gp_key: str, session_type: str = "R") -> list[dict]:
    """Extract race control messages (penalties, investigations, incidents)."""
    print(f"  📣 Race control: {year} {gp_key} ({session_type})")
    try:
        session = fastf1.get_session(year, gp_key, session_type)
        session.load(laps=False, telemetry=False, weather=False, messages=True)
    except Exception as e:
        print(f"    ⚠️  Could not load session: {e}")
        return []

    rcm = getattr(session, "race_control_messages", None)
    if rcm is None or rcm.empty:
        return []

    out = []
    for _, row in rcm.iterrows():
        category = str(row.get("Category", "")).strip()
        message = str(row.get("Message", "")).strip()
        if not message:
            continue
        # Keep the most meaningful event categories visible on website.
        if category and category.lower() not in {
            "track", "other", "car event"
        }:
            include = True
        else:
            include = any(k in message.lower() for k in [
                "penalty", "investigation", "safety car", "vsc",
                "red flag", "restart", "black and white", "incident"
            ])
        if not include:
            continue

        out.append({
            "time": str(row.get("Time", "")),
            "category": category or "Race Control",
            "message": message,
            "lap": int(row.get("Lap", 0) or 0),
            "driver": str(row.get("Driver", "")).strip() or None,
        })

    return out[:80]


# ═══════════════════════════════════════════════════════════════════════════
# Combined Telemetry Export
# ═══════════════════════════════════════════════════════════════════════════

def extract_telemetry_for_round(
    round_num: int,
    year: int = SEASON_YEAR,
    session_type: str = "Q",
) -> dict | None:
    """
    Extract all telemetry features for a given round.

    Returns dict ready for inclusion in round JSON:
      { speedTraps: [...], sectorTimes: [...] }
    """
    if round_num not in CALENDAR:
        print(f"  ⚠️  Round {round_num} not in calendar")
        return None

    gp_key = CALENDAR[round_num]["gp_key"]
    print(f"\n📡 Extracting telemetry for Round {round_num}: {CALENDAR[round_num]['name']}")

    try:
        speed_traps = extract_speed_traps(year, gp_key, session_type)
    except Exception as e:
        print(f"  ⚠️  speed traps failed: {e}")
        speed_traps = []

    try:
        sector_times = extract_sector_times(year, gp_key, session_type)
    except Exception as e:
        print(f"  ⚠️  sector times failed: {e}")
        sector_times = []

    # Race-session-specific enrichments (each isolated so partial data can still be exported)
    try:
        stints = extract_stint_timeline(year, gp_key, "R")
    except Exception as e:
        print(f"  ⚠️  stint timeline failed: {e}")
        stints = []

    try:
        track_status = extract_track_status_events(year, gp_key, "R")
    except Exception as e:
        print(f"  ⚠️  track status failed: {e}")
        track_status = []

    try:
        pit_impact = extract_pit_stop_impact(year, gp_key, "R")
    except Exception as e:
        print(f"  ⚠️  pit stop impact failed: {e}")
        pit_impact = []

    try:
        sector_dominance = extract_sector_dominance(year, gp_key, "R")
    except Exception as e:
        print(f"  ⚠️  sector dominance failed: {e}")
        sector_dominance = []

    try:
        race_control = extract_race_control_events(year, gp_key, "R")
    except Exception as e:
        print(f"  ⚠️  race control failed: {e}")
        race_control = []

    if not speed_traps and not sector_times and not stints and not track_status and not pit_impact and not sector_dominance and not race_control:
        print("  ⚠️  No telemetry data available")
        return None

    telemetry = {
        "speedTraps": speed_traps,
        "sectorTimes": sector_times,
        "stintTimeline": stints,
        "trackStatusEvents": track_status,
        "pitStopImpact": pit_impact,
        "sectorDominance": sector_dominance,
        "raceControlEvents": race_control,
    }

    print(
        f"  ✅ speed={len(speed_traps)}, sectorTimes={len(sector_times)}, "
        f"stints={len(stints)}, trackStatus={len(track_status)}, pitImpact={len(pit_impact)}, "
        f"sectorDominance={len(sector_dominance)}, raceControl={len(race_control)}"
    )
    return telemetry


def inject_telemetry_into_round_json(round_num: int, telemetry: dict) -> bool:
    """
    Inject telemetry data into an existing round JSON file.
    """
    round_path = os.path.join(WEBSITE_ROUNDS_DIR, f"round_{round_num:02d}.json")
    if not os.path.exists(round_path):
        print(f"  ⚠️  {round_path} doesn't exist — run export_website_data.py first")
        return False

    with open(round_path, "r") as f:
        data = json.load(f)

    data["telemetryData"] = telemetry

    with open(round_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"  💾 Telemetry injected → {round_path}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Extract telemetry features from FastF1")
    parser.add_argument("--round", type=int, help="Round number")
    parser.add_argument("--all", action="store_true", help="Process all rounds")
    parser.add_argument("--year", type=int, default=SEASON_YEAR, help=f"Year for session data (default: {SEASON_YEAR})")
    parser.add_argument("--session", default="Q", choices=["Q", "R", "FP1", "FP2", "FP3"],
                        help="Session type (default: Q for qualifying)")
    parser.add_argument("--inject", action="store_true",
                        help="Inject telemetry into existing round JSON files")
    args = parser.parse_args()

    enable_cache()

    rounds = list(CALENDAR.keys()) if args.all else [args.round] if args.round else []

    if not rounds:
        parser.print_help()
        return

    for rnd in rounds:
        telemetry = extract_telemetry_for_round(rnd, args.year, args.session)
        if telemetry and args.inject:
            inject_telemetry_into_round_json(rnd, telemetry)

    print("\n✅ Telemetry extraction complete!")


if __name__ == "__main__":
    main()
