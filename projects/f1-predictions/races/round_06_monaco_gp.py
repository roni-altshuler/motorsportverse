# %% [markdown]
# # 🏁 Monaco Grand Prix — Prediction
# **Round 6** | Circuit: Monaco | Date: 2026-06-07

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Monaco"
GP_ROUND    = 6
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.1
TEMPERATURE = 22

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 71.28,
    "ALO": 71.63,
    "ANT": 70.99,
    "BEA": 71.63,
    "BOR": 72.19,
    "BOT": 71.98,
    "COL": 71.98,
    "GAS": 71.42,
    "HAD": 71.35,
    "HAM": 70.85,
    "HUL": 71.84,
    "LAW": 70.99,
    "LEC": 70.71,
    "LIN": 72.12,
    "NOR": 70.64,
    "OCO": 71.7,
    "PER": 71.06,
    "PIA": 70.57,
    "RUS": 70.78,
    "SAI": 71.13,
    "STR": 71.91,
    "VER": 70.5,
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
classification = predicted_classification(merged, gp_name="Monaco Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Monaco Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Monaco Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Monaco Grand Prix prediction complete!")
