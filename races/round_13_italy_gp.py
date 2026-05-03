# %% [markdown]
# # 🏁 Italian Grand Prix — Prediction
# **Round 13** | Circuit: Monza | Date: 2026-09-06

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Italy"
GP_ROUND    = 13
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.1
TEMPERATURE = 26

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 80.37,
    "ALO": 80.77,
    "ANT": 80.06,
    "BEA": 80.77,
    "BOR": 81.41,
    "BOT": 81.17,
    "COL": 81.17,
    "GAS": 80.53,
    "HAD": 80.45,
    "HAM": 79.9,
    "HUL": 81.01,
    "LAW": 80.06,
    "LEC": 79.74,
    "LIN": 81.33,
    "NOR": 79.66,
    "OCO": 80.85,
    "PER": 80.14,
    "PIA": 79.58,
    "RUS": 79.82,
    "SAI": 80.22,
    "STR": 81.09,
    "VER": 79.5,
}

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
classification = predicted_classification(merged, gp_name="Italian Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Italian Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Italian Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Italian Grand Prix prediction complete!")
