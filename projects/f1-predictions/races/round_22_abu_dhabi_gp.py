# %% [markdown]
# # 🏁 Abu Dhabi Grand Prix — Prediction
# **Round 22** | Circuit: Yas Marina | Date: 2026-12-06

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Abu Dhabi"
GP_ROUND    = 22
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.02
TEMPERATURE = 28

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 84.92,
    "ALO": 85.34,
    "ANT": 84.59,
    "BEA": 85.34,
    "BOR": 86.02,
    "BOT": 85.76,
    "COL": 85.76,
    "GAS": 85.09,
    "HAD": 85.01,
    "HAM": 84.42,
    "HUL": 85.6,
    "LAW": 84.59,
    "LEC": 84.25,
    "LIN": 85.93,
    "NOR": 84.17,
    "OCO": 85.43,
    "PER": 84.67,
    "PIA": 84.08,
    "RUS": 84.34,
    "SAI": 84.76,
    "STR": 85.68,
    "VER": 84.0,
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
classification = predicted_classification(merged, gp_name="Abu Dhabi Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Abu Dhabi Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Abu Dhabi Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Abu Dhabi Grand Prix prediction complete!")
