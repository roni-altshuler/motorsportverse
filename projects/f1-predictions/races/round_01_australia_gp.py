# %% [markdown]
# # 🏁 Australian Grand Prix — Prediction
# **Round 1** | Circuit: Albert Park | Date: 2026-03-08

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Australia"
GP_ROUND    = 1
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.1
TEMPERATURE = 24

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 75.62,
    "ALO": 76.0,
    "ANT": 75.32,
    "BEA": 76.0,
    "BOR": 76.6,
    "BOT": 76.37,
    "COL": 76.37,
    "GAS": 75.77,
    "HAD": 75.7,
    "HAM": 75.17,
    "HUL": 76.22,
    "LAW": 75.32,
    "LEC": 75.02,
    "LIN": 76.52,
    "NOR": 74.95,
    "OCO": 76.07,
    "PER": 75.4,
    "PIA": 74.87,
    "RUS": 75.1,
    "SAI": 75.47,
    "STR": 76.3,
    "VER": 74.8,
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
classification = predicted_classification(merged, gp_name="Australian Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Australian Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Australian Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Australian Grand Prix prediction complete!")
