# %% [markdown]
# # 🏁 Singapore Grand Prix — Prediction
# **Round 16** | Circuit: Marina Bay | Date: 2026-10-11

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Singapore"
GP_ROUND    = 16
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.2
TEMPERATURE = 30

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 97.06,
    "ALO": 97.54,
    "ANT": 96.67,
    "BEA": 97.54,
    "BOR": 98.3,
    "BOT": 98.02,
    "COL": 98.02,
    "GAS": 97.25,
    "HAD": 97.15,
    "HAM": 96.48,
    "HUL": 97.82,
    "LAW": 96.67,
    "LEC": 96.29,
    "LIN": 98.21,
    "NOR": 96.19,
    "OCO": 97.63,
    "PER": 96.77,
    "PIA": 96.1,
    "RUS": 96.38,
    "SAI": 96.86,
    "STR": 97.92,
    "VER": 96.0,
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
classification = predicted_classification(merged, gp_name="Singapore Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Singapore Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Singapore Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Singapore Grand Prix prediction complete!")
