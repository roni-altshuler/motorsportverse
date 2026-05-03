# %% [markdown]
# # 🏁 Barcelona-Catalunya Grand Prix — Prediction
# **Round 7** | Circuit: Barcelona-Catalunya | Date: 2026-06-14

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Spain"
GP_ROUND    = 7
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.05
TEMPERATURE = 28

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 76.84,
    "ALO": 77.22,
    "ANT": 76.53,
    "BEA": 77.22,
    "BOR": 77.82,
    "BOT": 77.6,
    "COL": 77.6,
    "GAS": 76.99,
    "HAD": 76.91,
    "HAM": 76.38,
    "HUL": 77.44,
    "LAW": 76.53,
    "LEC": 76.23,
    "LIN": 77.75,
    "NOR": 76.15,
    "OCO": 77.29,
    "PER": 76.61,
    "PIA": 76.08,
    "RUS": 76.3,
    "SAI": 76.68,
    "STR": 77.52,
    "VER": 76.0,
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
classification = predicted_classification(merged, gp_name="Barcelona-Catalunya Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Barcelona-Catalunya Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Barcelona-Catalunya Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Barcelona-Catalunya Grand Prix prediction complete!")
