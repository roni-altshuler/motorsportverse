#!/usr/bin/env python3
"""
gp_weekend.py — Automated GP Weekend Pipeline
================================================
A single script that handles the entire Grand Prix weekend workflow:

  • Pre-weekend:  Generate predictions with live weather forecast
  • Post-quali:   Incorporate real qualifying data + telemetry from FastF1
  • Post-race:    Fetch actual results, update accuracy tracker, rebuild data

The script auto-detects which sessions are available on FastF1 and adapts
its behavior accordingly.

Usage:
    # Auto-detect round from calendar (picks the next upcoming race)
    python gp_weekend.py

    # Specify a round explicitly
    python gp_weekend.py --round 1

    # Force a specific phase
    python gp_weekend.py --round 1 --phase pre
    python gp_weekend.py --round 1 --phase post-quali
    python gp_weekend.py --round 1 --phase post-race

    # Run everything for the round (full rebuild)
    python gp_weekend.py --round 1 --full

    # Skip website build
    python gp_weekend.py --round 1 --no-build

    # Dry run (show what would happen without executing)
    python gp_weekend.py --round 1 --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

# ── Lazy imports (f1_prediction_utils requires fastf1) ──
# We import these inside functions so --help and --dry-run work fast.

WEBSITE_DIR = os.path.join(os.path.dirname(__file__), "website")
DATA_DIR = os.path.join(WEBSITE_DIR, "public", "data")


# ═════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════

def _load_calendar():
    """Load the calendar lazily from f1_prediction_utils."""
    from f1_prediction_utils import CALENDAR
    return CALENDAR


def _season_year():
    """Load the active season year lazily from f1_prediction_utils."""
    from f1_prediction_utils import SEASON_YEAR
    return int(SEASON_YEAR)


def _utc_today():
    """Return today's date, with optional override for deterministic tests."""
    override = os.getenv("F1_WEEKEND_TODAY")
    if override:
        return date.fromisoformat(override)
    return date.today()


def _utc_now():
    """Return the current UTC datetime, with optional override for tests."""
    override = os.getenv("F1_WEEKEND_NOW_UTC")
    if override:
        return datetime.fromisoformat(override)
    return datetime.utcnow()


def _weekend_window(round_num):
    """Return the active automation window for a round.

    The pipeline should begin publishing previews before the weekend and
    continue retrying shortly after the race finishes to catch delayed
    FastF1 result availability.
    """
    cal = _load_calendar()
    race_date = date.fromisoformat(cal[round_num]["date"])
    return race_date - timedelta(days=3), race_date + timedelta(days=2)


def is_race_weekend(round_num, today=None):
    """True when a round is in the automation window."""
    cal = _load_calendar()
    if cal[round_num].get("postponed", False):
        return False
    today = today or _utc_today()
    start, end = _weekend_window(round_num)
    return start <= today <= end


def detect_target_round(today=None):
    """Find the active race weekend, otherwise the next upcoming round."""
    cal = _load_calendar()
    today = today or _utc_today()

    for rnd in sorted(cal.keys()):
        if cal[rnd].get("postponed", False):
            continue
        if is_race_weekend(rnd, today=today):
            return rnd

    for rnd in sorted(cal.keys()):
        if cal[rnd].get("postponed", False):
            continue
        race_date = date.fromisoformat(cal[rnd]["date"])
        if race_date >= today:
            return rnd

    return max(cal.keys())


def _detect_next_round():
    """Backwards-compatible wrapper for the next active/upcoming GP."""
    return detect_target_round()


def _session_available(year, gp_key, session_type):
    """Check if a FastF1 session has data (qualifying or race happened)."""
    try:
        import fastf1
        import concurrent.futures

        def _probe():
            s = fastf1.get_session(year, gp_key, session_type)
            s.load(laps=True, telemetry=False, weather=False, messages=False)
            return len(s.laps) > 0

        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            return ex.submit(_probe).result(timeout=20)
    except Exception:
        return False


def _detect_phase(round_num):
    """Auto-detect which phase we're in based on data availability."""
    cal = _load_calendar()
    info = cal[round_num]
    if info.get("postponed", False):
        print(f"\n⏸️  Round {round_num}: {info['name']} is postponed. Skipping auto phase detection.")
        return "pre"
    gp_key = info["gp_key"]
    race_date = date.fromisoformat(info["date"])
    today = _utc_today()

    print(f"\n🔍 Detecting phase for Round {round_num}: {info['name']}")
    print(f"   Race date: {info['date']} | Today: {today}")

    # If race day hasn't happened yet, no need to probe FastF1
    if today < race_date:
        # Qualifying is typically the day before the race
        quali_date = race_date - timedelta(days=1)
        if today >= quali_date:
            # It's Saturday — qualifying might have just happened
            print("   📅 Qualifying day — checking for data...")
        else:
            print("   📅 Before qualifying → pre")
            return "pre"

    # Race date passed — check what's available
    from f1_prediction_utils import enable_cache
    enable_cache()

    if today >= race_date:
        season_year = _season_year()
        # Check if race data is available for the configured season.
        if _session_available(season_year, gp_key, "R"):
            print("   ✅ Race data available → post-race")
            return "post-race"

    # Check if qualifying data is available for the configured season.
    if today >= race_date - timedelta(days=1):
        season_year = _season_year()
        if _session_available(season_year, gp_key, "Q"):
            print("   ✅ Qualifying data available → post-quali")
            return "post-quali"

    print("   📅 No session data yet → pre")
    return "pre"


def _print_banner(title, char="═"):
    width = 70
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}\n")


# ═════════════════════════════════════════════════════════════════════════
# Phase Runners
# ═════════════════════════════════════════════════════════════════════════

def run_pre_weekend(round_num, skip_build=False, use_race_simulator=False):
    """Phase 1: Pre-weekend predictions with weather forecast.

    Run this on Thursday/Friday before the race weekend.
    Generates ML predictions using historical data + live weather.
    """
    _print_banner(f"PHASE 1: PRE-WEEKEND PREDICTIONS (Round {round_num})")

    from export_website_data import (
        export_round_data, export_standings, export_season_metadata
    )

    # Generate predictions with weather API
    print("📊 Generating ML predictions with live weather forecast...")
    round_data, merged = export_round_data(
        round_num,
        return_merged=True,
        use_lstm=False,        # LSTM not needed in pre-phase
        use_weather_api=True,  # live weather forecast
        use_telemetry=False,   # no telemetry yet
        use_race_simulator=use_race_simulator,
        prediction_phase="preview",
    )

    # Update metadata
    export_standings()
    export_season_metadata()

    print(f"\n✅ Pre-weekend prediction complete for Round {round_num}")
    print(f"   Predicted winner: {round_data['classification'][0]['driver']} "
          f"({round_data['classification'][0]['team']})")

    if not skip_build:
        _build_website()

    return round_data, merged


def run_post_qualifying(round_num, skip_build=False, use_race_simulator=False):
    """Phase 2: Post-qualifying update with real data.

    Run this after qualifying on Saturday.
    Re-runs predictions using actual qualifying times from FastF1,
    adds telemetry, and runs advanced models.
    """
    _print_banner(f"PHASE 2: POST-QUALIFYING UPDATE (Round {round_num})")

    from export_website_data import (
        export_round_data, export_standings, export_season_metadata,
        _run_advanced, _generate_fastf1_viz, ROUNDS_DIR, CALENDAR
    )
    import json

    # Re-run predictions — fetch_qualifying_data will auto-detect
    # and use real qualifying times from FastF1
    print("🏁 Regenerating predictions with REAL qualifying data...")
    round_data, merged = export_round_data(
        round_num,
        return_merged=True,
        use_lstm=True,          # full ensemble with LSTM
        use_weather_api=True,   # updated weather (closer to race)
        use_telemetry=True,     # speed traps + sector times from quali
        use_race_simulator=use_race_simulator,
        prediction_phase="post-quali",
    )

    # Generate FastF1 historical visualizations
    print("\n🏎️  Generating FastF1 visualizations...")
    gp_key = CALENDAR[round_num]["gp_key"]
    season_year = _season_year()
    try:
        extra = _generate_fastf1_viz(round_num, gp_key, season_year)
        if extra:
            round_data["visualizations"].extend(extra)
            path = os.path.join(ROUNDS_DIR, f"round_{round_num:02d}.json")
            with open(path, "w") as f:
                json.dump(round_data, f, indent=2)
    except Exception as e:
        print(f"  ⚠️  FastF1 viz failed: {e}")

    # Run advanced models (pit strategy, tyre deg, LSTM viz, tracker)
    print("\n⛽ Running advanced strategy models...")
    _run_advanced(round_data, merged)

    # Update metadata
    export_standings()
    export_season_metadata()

    print(f"\n✅ Post-qualifying update complete for Round {round_num}")
    print(f"   Predicted winner: {round_data['classification'][0]['driver']} "
          f"({round_data['classification'][0]['team']})")

    if not skip_build:
        _build_website()

    return round_data, merged


def run_post_race(round_num, skip_build=False):
    """Phase 3: Post-race results and accuracy update.

    Run this after the race on Sunday.
    Fetches actual race results from FastF1, updates the accuracy
    tracker, and regenerates visualizations.
    """
    _print_banner(f"PHASE 3: POST-RACE RESULTS (Round {round_num})")

    from f1_prediction_utils import (
        CALENDAR, enable_cache, save_race_result
    )
    from advanced_models import SeasonTracker
    from export_website_data import (
        export_standings, export_season_metadata, ROUNDS_DIR, _write_gp_accuracy_report
    )
    import pandas as pd

    enable_cache()
    info = CALENDAR[round_num]
    gp_key = info["gp_key"]

    # Fetch actual race results from FastF1
    print("🏁 Fetching actual race results from FastF1...")
    actual_results = _fetch_actual_race_results(gp_key, year=_season_year())

    if not actual_results:
        print("⚠️  Could not fetch race results. Session may not be available yet.")
        print("   Try again later or manually add results.")
        return None

    print(f"   ✅ Got results for {len(actual_results)} drivers")

    # Display results
    print("\n📋 Actual Race Results:")
    for drv, pos in sorted(actual_results.items(), key=lambda x: x[1]):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, "  ")
        print(f"   {medal} P{pos:>2}  {drv}")

    # Save actual results for race-to-race feature tracking
    print("\n💾 Saving actual results for future predictions...")
    # Build a classification-like DataFrame for save_race_result
    clf_data = pd.DataFrame([
        {"Driver": drv, "Pos": pos}
        for drv, pos in actual_results.items()
    ]).set_index("Pos").sort_index()
    save_race_result(round_num, clf_data)

    # Update the season accuracy tracker
    print("\n📊 Updating accuracy tracker...")
    tracker = SeasonTracker()
    tracker.add_actual_result(round_num, actual_results)

    # Export tracker data for website
    tracker_export = tracker.export_for_website()
    tracker_path = SeasonTracker.WEBSITE_TRACKER_FILE
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)
    with open(tracker_path, "w") as f:
        json.dump(tracker_export, f, indent=2)
    print(f"   ✅ Season tracker updated → {tracker_path}")
    _write_gp_accuracy_report(tracker_export)

    round_report = tracker.get_round_report(round_num)

    # Print accuracy for this round
    accuracy = tracker.data["accuracy"].get(str(round_num), {})
    if accuracy:
        print(f"\n📈 Round {round_num} Accuracy:")
        print(f"   Mean position error: {accuracy.get('mean_position_error', '?')}")
        print(f"   Exact matches:       {accuracy.get('exact_matches', '?')}/{accuracy.get('total_drivers', '?')}")
        print(f"   Within 3 positions:  {accuracy.get('within_3_positions', '?')}/{accuracy.get('total_drivers', '?')} "
              f"({accuracy.get('accuracy_pct', '?')}%)")

    # Inject actual results into the round JSON for the website
    round_path = os.path.join(ROUNDS_DIR, f"round_{round_num:02d}.json")
    if os.path.exists(round_path):
        with open(round_path) as f:
            round_data = json.load(f)
        round_data["actualResults"] = actual_results
        round_data["accuracy"] = accuracy
        round_data["trackerData"] = tracker_export
        if round_report:
            round_data["gpReport"] = round_report
        with open(round_path, "w") as f:
            json.dump(round_data, f, indent=2)
        print(f"   ✅ Actual results injected → {round_path}")

    # Update metadata
    export_standings()
    export_season_metadata()

    print(f"\n✅ Post-race update complete for Round {round_num}")

    if not skip_build:
        _build_website()

    return actual_results


def _fetch_actual_race_results(gp_key, year=None):
    """Fetch actual race classification from FastF1."""
    season_year = _season_year() if year is None else int(year)
    try:
        import fastf1
        import pandas as pd
        import concurrent.futures

        def _load():
            s = fastf1.get_session(season_year, gp_key, "R")
            s.load(laps=False, telemetry=False, weather=False, messages=False)
            return s

        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            session = ex.submit(_load).result(timeout=30)

        results = session.results
        if results is None or results.empty:
            return None

        actual = {}
        for _, row in results.iterrows():
            abbr = row.get("Abbreviation", "")
            pos = row.get("Position", None)
            if abbr and pos is not None and not pd.isna(pos):
                actual[abbr] = int(pos)

        return actual if actual else None

    except Exception as e:
        print(f"   ⚠️  FastF1 race results fetch failed: {e}")
        return None


def _build_website():
    """Rebuild the Next.js website."""
    _print_banner("REBUILDING WEBSITE", "─")
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=WEBSITE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            print("✅ Website built successfully!")
        else:
            print(f"⚠️  Website build failed:\n{result.stderr[-500:]}")
    except FileNotFoundError:
        print("⚠️  npm not found. Build the website manually: cd website && npm run build")
    except subprocess.TimeoutExpired:
        print("⚠️  Website build timed out (3 min). Try manually.")


# ═════════════════════════════════════════════════════════════════════════
# Full Pipeline
# ═════════════════════════════════════════════════════════════════════════

def run_full(round_num, skip_build=False, use_race_simulator=False):
    """Run all phases sequentially (for testing or catch-up)."""
    _print_banner(f"FULL PIPELINE: Round {round_num}", "█")

    rd, merged = run_pre_weekend(round_num, skip_build=True, use_race_simulator=use_race_simulator)

    # Try post-quali (may fail if qualifying hasn't happened)
    try:
        rd, merged = run_post_qualifying(round_num, skip_build=True, use_race_simulator=use_race_simulator)
    except Exception as e:
        print(f"\n⚠️  Post-qualifying skipped: {e}")

    # Try post-race (may fail if race hasn't happened)
    try:
        run_post_race(round_num, skip_build=True)
    except Exception as e:
        print(f"\n⚠️  Post-race skipped: {e}")

    if not skip_build:
        _build_website()

    print(f"\n🏁 Full pipeline complete for Round {round_num}!")


# ═════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="🏎️  F1 GP Weekend Automation — single script for the entire race weekend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gp_weekend.py                       # Auto-detect round & phase
  python gp_weekend.py --round 1             # Auto-detect phase for Round 1
  python gp_weekend.py --round 1 --phase pre # Force pre-weekend phase
  python gp_weekend.py --round 1 --full      # Run all phases
  python gp_weekend.py --dry-run             # Show what would happen

Typical GP Weekend Workflow:
  Thursday:   python gp_weekend.py --phase pre
  Saturday:   python gp_weekend.py --phase post-quali
  Sunday:     python gp_weekend.py --phase post-race
  Or just:    python gp_weekend.py   (auto-detects everything!)
        """,
    )
    parser.add_argument("--round", type=int,
                        help="Round number (1-24). Auto-detects next upcoming race if omitted.")
    parser.add_argument("--phase", choices=["pre", "post-quali", "post-race"],
                        help="Force a specific phase. Auto-detects if omitted.")
    parser.add_argument("--full", action="store_true",
                        help="Run all phases sequentially (pre → post-quali → post-race)")
    parser.add_argument("--no-build", action="store_true",
                        help="Skip website rebuild after data generation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be executed without actually running")
    parser.add_argument("--use-race-simulator", action="store_true",
                        help="Splice per-lap MC race simulator probabilities into round JSON "
                             "(requires a registered race-pace ensemble — run train_race_pace.py first).")
    args = parser.parse_args()

    # ── Resolve round ──
    if args.round:
        round_num = args.round
        cal = _load_calendar()
        info = cal[round_num]
        print(f"🏎️  Round {round_num}: {info['name']} ({info['date']})")
    else:
        round_num = detect_target_round()
        cal = _load_calendar()
        info = cal[round_num]
        print(f"🏎️  Auto-detected Round {round_num}: {info['name']} ({info['date']})")

    # ── Resolve phase ──
    if args.full:
        phase = "full"
    elif args.phase:
        phase = args.phase
    else:
        phase = _detect_phase(round_num)

    if info.get("postponed", False) and phase != "post-race":
        print(f"\n⏸️  {info['name']} is marked as postponed. No pre-weekend or qualifying automation will run until a new date is set.")
        return

    # ── Dry run ──
    if args.dry_run:
        _print_banner("DRY RUN — Would execute:")
        phase_descriptions = {
            "pre":        "Pre-weekend predictions (ML + weather forecast)",
            "post-quali": "Post-qualifying update (real quali data + telemetry + advanced models + FastF1 viz)",
            "post-race":  "Post-race results (fetch actual results + update accuracy tracker)",
            "full":       "Full pipeline (all three phases sequentially)",
        }
        print(f"  Round:   {round_num} — {info['name']}")
        print(f"  Phase:   {phase}")
        print(f"  Action:  {phase_descriptions[phase]}")
        print(f"  Build:   {'No' if args.no_build else 'Yes'}")
        print()
        commands = {
            "pre":        f"export_round_data({round_num}, use_weather_api=True)",
            "post-quali": f"export_round_data({round_num}, use_lstm=True, use_weather_api=True, use_telemetry=True) + FastF1 viz + advanced models",
            "post-race":  "Fetch race results from FastF1 → update SeasonTracker → inject into round JSON",
            "full":       "pre → post-quali → post-race (all phases)",
        }
        print(f"  Pipeline: {commands[phase]}")
        return

    # ── Execute ──
    if phase == "full":
        run_full(round_num, skip_build=args.no_build, use_race_simulator=args.use_race_simulator)
    elif phase == "pre":
        run_pre_weekend(round_num, skip_build=args.no_build, use_race_simulator=args.use_race_simulator)
    elif phase == "post-quali":
        run_post_qualifying(round_num, skip_build=args.no_build, use_race_simulator=args.use_race_simulator)
    elif phase == "post-race":
        run_post_race(round_num, skip_build=args.no_build)

    _print_banner("🏁 DONE", "═")


if __name__ == "__main__":
    main()
