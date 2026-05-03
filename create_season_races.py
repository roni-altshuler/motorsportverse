#!/usr/bin/env python3
"""
create_season_races.py
======================
Generates a prediction script for each round of the configured season.

Usage:
    python create_season_races.py

Creates:
    races/round_01_australian_gp.py
    races/round_02_chinese_gp.py
    ...
    races/round_22_abu_dhabi_gp.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))
from f1_prediction_utils import (
    CALENDAR, SEASON_YEAR, CIRCUIT_CHARACTERISTICS, DRIVER_QUALI_OFFSET,
    generate_qualifying_estimates,
)


# ---- Weather estimates per GP (rough defaults) ---------------------------
GP_WEATHER = {
    "Australia":      {"rain": 0.10, "temp": 24},
    "China":          {"rain": 0.15, "temp": 18},
    "Japan":          {"rain": 0.20, "temp": 16},
    "Miami":          {"rain": 0.15, "temp": 30},
    "Monaco":         {"rain": 0.10, "temp": 22},
    "Spain":          {"rain": 0.05, "temp": 28},
    "Madrid":         {"rain": 0.08, "temp": 27},
    "Canada":         {"rain": 0.25, "temp": 20},
    "Austria":        {"rain": 0.30, "temp": 22},
    "Great Britain":  {"rain": 0.35, "temp": 18},
    "Belgium":        {"rain": 0.40, "temp": 17},
    "Hungary":        {"rain": 0.15, "temp": 30},
    "Netherlands":    {"rain": 0.30, "temp": 18},
    "Italy":          {"rain": 0.10, "temp": 26},
    "Azerbaijan":     {"rain": 0.05, "temp": 22},
    "Singapore":      {"rain": 0.20, "temp": 30},
    "United States":  {"rain": 0.10, "temp": 24},
    "Mexico":         {"rain": 0.15, "temp": 20},
    "Brazil":         {"rain": 0.30, "temp": 24},
    "Las Vegas":      {"rain": 0.02, "temp": 14},
    "Qatar":          {"rain": 0.02, "temp": 28},
    "Abu Dhabi":      {"rain": 0.02, "temp": 28},
}

# ---- Historical years available per GP -----------------------------------
# Which years of data are available for each GP location in FastF1
GP_DATA_YEARS = {
    "Australia":      [2023, 2024, 2025],
    "China":          [2024, 2025],
    "Japan":          [2023, 2024, 2025],
    "Miami":          [2023, 2024, 2025],
    "Monaco":         [2023, 2024, 2025],
    "Spain":          [2023, 2024, 2025],
    "Madrid":         [2023, 2024, 2025],
    "Canada":         [2023, 2024, 2025],
    "Austria":        [2023, 2024, 2025],
    "Great Britain":  [2023, 2024, 2025],
    "Belgium":        [2023, 2024, 2025],
    "Hungary":        [2023, 2024, 2025],
    "Netherlands":    [2023, 2024, 2025],
    "Italy":          [2023, 2024, 2025],
    "Azerbaijan":     [2023, 2024, 2025],
    "Singapore":      [2023, 2024, 2025],
    "United States":  [2023, 2024, 2025],
    "Mexico":         [2023, 2024, 2025],
    "Brazil":         [2023, 2024, 2025],
    "Las Vegas":      [2023, 2024, 2025],
    "Qatar":          [2023, 2024, 2025],
    "Abu Dhabi":      [2023, 2024, 2025],
}


def _safe(s):
    return s.replace(" ", "_").replace("—", "-").replace("ã", "a").replace("é", "e")


def generate_race_file(round_num, info):
    """Generate the Python prediction script for one GP round."""
    gp_key  = info["gp_key"]
    name    = info["name"]
    weather = GP_WEATHER.get(gp_key, {"rain": 0.10, "temp": 22})
    years   = GP_DATA_YEARS.get(gp_key, [2023, 2024, 2025])

    # Auto-generate qualifying estimates
    quali = generate_qualifying_estimates(gp_key)
    quali_str = "{\n"
    for drv, t in sorted(quali.items()):
        quali_str += f'    "{drv}": {t},\n'
    quali_str += "}"

    content = f'''# %% [markdown]
# # 🏁 {name} — Prediction
# **Round {round_num}** | Circuit: {info["circuit"]} | Date: {info["date"]}

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "{gp_key}"
GP_ROUND    = {round_num}
GP_YEARS    = {years}
RAIN_PROB   = {weather["rain"]}
TEMPERATURE = {weather["temp"]}

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {quali_str}

# %% — Load historical data
laps = load_multi_year_data(GP_NAME, GP_YEARS)

# %% — Aggregate driver statistics
driver_stats = aggregate_driver_stats(laps)

# %% — Build enriched grid
grid   = build_grid_dataframe()
merged = build_training_dataset(grid, driver_stats,
                                circuit_key=GP_NAME,
                                current_round=GP_ROUND)

# %% — Get qualifying data (auto-fetch or estimates)
qualifying_times = get_qualifying_or_estimates(SEASON_YEAR, GP_NAME, QUALIFYING_ESTIMATES)
merged = apply_qualifying_data(merged, qualifying_times,
                               rain_probability=RAIN_PROB,
                               temperature_c=TEMPERATURE)

# %% — Train ensemble model
results = train_ensemble(merged, max_spread_s=3.5)

# %% — Evaluate
metrics = evaluate_models(results)
merged  = results["merged"]

# %% — Classification
classification = predicted_classification(merged, gp_name="{name}")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="{name}")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="{name}", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\\n✅ {name} prediction complete!")
'''
    return content


def main():
    os.makedirs("races", exist_ok=True)
    print(f"🏗️  Generating {SEASON_YEAR} season prediction scripts …\n")

    expected_files = {
        f"round_{rnd:02d}_{_safe(info['gp_key']).lower()}_gp.py"
        for rnd, info in sorted(CALENDAR.items())
    }
    for fname in os.listdir("races"):
        if fname.startswith("round_") and fname.endswith("_gp.py") and fname not in expected_files:
            os.remove(os.path.join("races", fname))
            print(f"  🧹 Removed stale generated script: races/{fname}")

    for rnd, info in sorted(CALENDAR.items()):
        fname = f"round_{rnd:02d}_{_safe(info['gp_key']).lower()}_gp.py"
        path  = os.path.join("races", fname)
        content = generate_race_file(rnd, info)
        with open(path, "w") as f:
            f.write(content)
        print(f"  ✅ {path:<50s}  Round {rnd:>2}: {info['name']}")

    print(f"\n🏁 {len(CALENDAR)} race prediction scripts generated in ./races/")
    print("   Run any race with:  python races/round_XX_<gp>_gp.py")


if __name__ == "__main__":
    main()
