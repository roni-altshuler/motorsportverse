#!/usr/bin/env python3
"""
generate_fastf1_viz.py
======================
Generate FastF1-powered visualizations for the website.

Visualizations:
  1. Track maps with annotated corners (per circuit)
  2. Driver lap time distributions (per race)
  3. Tyre strategy / stint analysis
  4. Speed traces

Based on FastF1 examples gallery:
  https://docs.fastf1.dev/gen_modules/examples_gallery/index.html

Usage:
    python generate_fastf1_viz.py --circuit Australia --year <season-year>
    python generate_fastf1_viz.py --all-circuits --year <season-year>
"""

import argparse
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import seaborn as sns  # noqa: F401 — used implicitly by some sub-plotters
import fastf1
import fastf1.plotting

sys.path.insert(0, os.path.dirname(__file__))
from f1_prediction_utils import (
    CALENDAR, TEAM_COLOURS, SEASON_YEAR,
)
# Design-system rcParams + palette.  Imported AFTER fastf1.plotting so
# our colour conventions win over FastF1's default styling.
import viz_style
from viz_style import VIZ_COLORS

VIZ_DIR = os.path.join("website", "public", "visualizations")

fastf1.plotting.setup_mpl(misc_mpl_mods=False)
# Re-apply design-system rcParams after fastf1.plotting.setup_mpl overrides them.
viz_style.apply_viz_style(force=True)

# Background used across this file's figures — match the website surface.
_BG = VIZ_COLORS["bg"]


def enable_cache():
    os.makedirs("f1_cache", exist_ok=True)
    fastf1.Cache.enable_cache("f1_cache")


def _save(fig, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  💾 {path}")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
# 1. TRACK MAP WITH ANNOTATED CORNERS
# ═══════════════════════════════════════════════════════════════════════════

def _load_race_session(year, gp_key, expected_round=None, telemetry=False):
    """Load the race session, verifying FastF1 resolved the requested event.

    FastF1's fuzzy matcher silently "corrects" an event name to a different
    (already-run) event when its schedule backend fails — that must never
    render another circuit's charts under this round's directory.
    """
    session = fastf1.get_session(year, gp_key, "R")
    if expected_round is not None and int(session.event["RoundNumber"]) != int(expected_round):
        raise ValueError(
            f"FastF1 resolved '{gp_key}' to round {session.event['RoundNumber']} "
            f"({session.event.get('EventName', '?')}), not round {expected_round}"
        )
    session.load(laps=True, telemetry=telemetry, weather=False, messages=False)
    return session


def plot_track_map(year, gp_key, out_dir, expected_round=None):
    """Draw the circuit layout with corner numbers annotated.

    Based on: https://docs.fastf1.dev/gen_modules/examples_gallery/general/plot_annotate_corners.html
    """
    print(f"  🗺️  Track map: {year} {gp_key}")
    try:
        session = _load_race_session(year, gp_key, expected_round, telemetry=True)

        lap = session.laps.pick_fastest()
        tel = lap.get_telemetry()

        x = tel["X"].values
        y = tel["Y"].values

        # Get circuit info for corners
        circuit_info = session.get_circuit_info()
        corners = circuit_info.corners

        fig, ax = plt.subplots(figsize=(12, 10), facecolor=_BG)
        ax.set_facecolor(_BG)

        # Plot track as colored line based on speed
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        speed = tel["Speed"].values
        norm = plt.Normalize(speed.min(), speed.max())
        lc = LineCollection(segments, cmap="plasma", norm=norm, linewidth=4)
        lc.set_array(speed[:-1])
        ax.add_collection(lc)

        # Auto-scale axes to fit the track (LineCollection doesn't do this)
        pad = 500  # metres of padding
        ax.set_xlim(x.min() - pad, x.max() + pad)
        ax.set_ylim(y.min() - pad, y.max() + pad)

        # Annotate corners
        for _, corner in corners.iterrows():
            txt = f"{int(corner['Number'])}"
            offset_x = corner.get("X", 0)
            offset_y = corner.get("Y", 0)
            ax.annotate(
                txt,
                xy=(offset_x, offset_y),
                fontsize=10,
                fontweight="bold",
                color=VIZ_COLORS["text"],
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=VIZ_COLORS["accent"],
                          edgecolor=VIZ_COLORS["text"], alpha=0.9),
            )

        cbar = plt.colorbar(lc, ax=ax, label="Speed (km/h)", shrink=0.7)
        cbar.ax.yaxis.label.set_color(VIZ_COLORS["text"])
        cbar.ax.tick_params(colors=VIZ_COLORS["text"])

        ax.set_title(f"{gp_key} — Circuit Map", fontsize=18, fontweight="bold", color=VIZ_COLORS["text"])
        ax.set_aspect("equal")
        ax.axis("off")
        plt.tight_layout()
        _save(fig, os.path.join(out_dir, "track_map.png"))
        return True
    except Exception as e:
        print(f"  ⚠️  Track map failed for {gp_key}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# 2. DRIVER LAP TIME DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════

def plot_laptime_distribution(year, gp_key, out_dir, expected_round=None):
    """Box plot of driver lap times (like fastest lap analysis).

    Based on: https://docs.fastf1.dev/gen_modules/examples_gallery/lap_times/plot_laptimes_distribution.html
    """
    print(f"  📊 Lap time distribution: {year} {gp_key}")
    try:
        session = _load_race_session(year, gp_key, expected_round)

        laps = session.laps.copy()
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        laps = laps[laps["LapTimeSec"].notna()]

        # Filter out outliers (pit laps, safety car, etc.)
        q1 = laps["LapTimeSec"].quantile(0.05)
        q3 = laps["LapTimeSec"].quantile(0.95)
        laps = laps[(laps["LapTimeSec"] >= q1) & (laps["LapTimeSec"] <= q3)]

        # Order by median lap time
        driver_order = (laps.groupby("Driver")["LapTimeSec"].median()
                        .sort_values().index.tolist())

        fig, ax = plt.subplots(figsize=(16, 10), facecolor=_BG)
        ax.set_facecolor(_BG)

        # Get team colors for each driver
        driver_colors = []
        for drv in driver_order:
            team = laps[laps["Driver"] == drv]["Team"].iloc[0] if "Team" in laps.columns else ""
            color = TEAM_COLOURS.get(team, "#888888")
            driver_colors.append(color)

        bp = ax.boxplot(
            [laps[laps["Driver"] == drv]["LapTimeSec"].values for drv in driver_order],
            labels=driver_order,
            patch_artist=True,
            vert=True,
            showfliers=False,
        )

        for patch, color in zip(bp["boxes"], driver_colors):
            patch.set_facecolor(color + "80")
            patch.set_edgecolor(color)
            patch.set_linewidth(2)
        for element in ["whiskers", "caps"]:
            for line in bp[element]:
                line.set_color(VIZ_COLORS["text"])
                line.set_linewidth(1.5)
        for median in bp["medians"]:
            median.set_color(VIZ_COLORS["text"])
            median.set_linewidth(2)

        ax.set_ylabel("Lap Time (s)", fontsize=14, color=VIZ_COLORS["text"])
        ax.set_title(f"{year} {gp_key} — Driver Lap Time Distribution",
                     fontsize=18, fontweight="bold", color=VIZ_COLORS["text"])
        ax.tick_params(colors=VIZ_COLORS["text"], labelsize=11)
        ax.spines["bottom"].set_color(VIZ_COLORS["text"])
        ax.spines["left"].set_color(VIZ_COLORS["text"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", alpha=0.2, color=VIZ_COLORS["text"])
        plt.xticks(rotation=45)
        plt.tight_layout()
        _save(fig, os.path.join(out_dir, "laptime_distribution_historical.png"))
        return True
    except Exception as e:
        print(f"  ⚠️  Lap time distribution failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# 3. TYRE STRATEGY OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════

def plot_tyre_strategy(year, gp_key, out_dir, expected_round=None):
    """Visualize tyre compound usage and stint lengths.

    Shows which compounds each driver used and for how many laps.
    """
    print(f"  🔴🟡⚪ Tyre strategy: {year} {gp_key}")
    try:
        session = _load_race_session(year, gp_key, expected_round)

        laps = session.laps.copy()
        if "Compound" not in laps.columns:
            print("    ⚠️  No compound data available")
            return False

        drivers = session.results["Abbreviation"].tolist()
        compound_colors = {
            "SOFT": "#FF3333", "MEDIUM": "#FFC300", "HARD": "#FFFFFF",
            "INTERMEDIATE": "#39B54A", "WET": "#0067AD",
        }

        fig, ax = plt.subplots(figsize=(16, 10), facecolor=_BG)
        ax.set_facecolor(_BG)

        for i, drv in enumerate(drivers):
            drv_laps = laps[laps["Driver"] == drv].sort_values("LapNumber")
            if drv_laps.empty:
                continue

            # Detect stints
            prev_compound = None
            stint_start = 0
            for _, lap in drv_laps.iterrows():
                compound = lap.get("Compound", "UNKNOWN")
                lap_num = int(lap["LapNumber"])
                if compound != prev_compound and prev_compound is not None:
                    color = compound_colors.get(prev_compound, "#888")
                    ax.barh(i, lap_num - stint_start, left=stint_start,
                            color=color, edgecolor=_BG, height=0.8)
                    stint_start = lap_num
                prev_compound = compound

            # Final stint
            if prev_compound:
                color = compound_colors.get(prev_compound, "#888")
                last_lap = int(drv_laps["LapNumber"].max())
                ax.barh(i, last_lap - stint_start + 1, left=stint_start,
                        color=color, edgecolor=_BG, height=0.8)

        ax.set_yticks(range(len(drivers)))
        ax.set_yticklabels(drivers, fontsize=10, color=VIZ_COLORS["text"])
        ax.set_xlabel("Lap Number", fontsize=13, color=VIZ_COLORS["text"])
        ax.set_title(f"{year} {gp_key} — Tyre Strategy", fontsize=18,
                     fontweight="bold", color=VIZ_COLORS["text"])
        ax.tick_params(colors=VIZ_COLORS["text"])
        ax.invert_yaxis()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(VIZ_COLORS["text"])
        ax.spines["left"].set_color(VIZ_COLORS["text"])

        legend_patches = [mpatches.Patch(color=c, label=l)
                         for l, c in compound_colors.items()]
        ax.legend(handles=legend_patches, loc="lower right", fontsize=10,
                 facecolor=_BG, edgecolor=VIZ_COLORS["text"], labelcolor=VIZ_COLORS["text"])

        plt.tight_layout()
        _save(fig, os.path.join(out_dir, "tyre_strategy.png"))
        return True
    except Exception as e:
        print(f"  ⚠️  Tyre strategy failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def generate_all_for_circuit(gp_key, year=SEASON_YEAR, round_num=1):
    """Generate all FastF1 visualizations for one circuit."""
    out_dir = os.path.join(VIZ_DIR, f"round_{round_num:02d}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Generating FastF1 visualizations: {gp_key} ({year})")
    print(f"{'='*60}")

    enable_cache()

    # Round numbers are only meaningful against the season being loaded —
    # the same circuit sits at a different round in historical seasons, so the
    # wrong-event guard applies only to current-season loads.
    check_round = round_num if int(year) == int(SEASON_YEAR) else None
    results = {
        "track_map": plot_track_map(year, gp_key, out_dir, expected_round=check_round),
        "laptime_dist": plot_laptime_distribution(year, gp_key, out_dir, expected_round=check_round),
        "tyre_strategy": plot_tyre_strategy(year, gp_key, out_dir, expected_round=check_round),
    }

    success = sum(1 for v in results.values() if v)
    print(f"\n✅ {success}/{len(results)} visualizations generated for {gp_key}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Generate FastF1 visualizations")
    parser.add_argument("--circuit", type=str, help="GP key (e.g. Australia)")
    parser.add_argument("--year", type=int, default=SEASON_YEAR, help="Year for historical data")
    parser.add_argument("--round", type=int, default=1, help="Round number")
    parser.add_argument("--all-circuits", action="store_true", help=f"All {SEASON_YEAR} circuits")
    args = parser.parse_args()

    if args.all_circuits:
        for rnd, info in sorted(CALENDAR.items()):
            try:
                generate_all_for_circuit(info["gp_key"], args.year, rnd)
            except Exception as e:
                print(f"⚠️  {info['gp_key']} failed: {e}")
    elif args.circuit:
        generate_all_for_circuit(args.circuit, args.year, args.round)
    else:
        generate_all_for_circuit("Australia", SEASON_YEAR, 1)


if __name__ == "__main__":
    main()
