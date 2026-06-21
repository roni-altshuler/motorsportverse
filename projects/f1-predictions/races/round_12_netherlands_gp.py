# %% [markdown]
# # 🏁 Dutch Grand Prix — Prediction
# **Round 12** | Circuit: Zandvoort | Date: 2026-08-23

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Netherlands"
GP_ROUND    = 12
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.3
TEMPERATURE = 18

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 70.77,
    "ALO": 71.12,
    "ANT": 70.49,
    "BEA": 71.12,
    "BOR": 71.68,
    "BOT": 71.47,
    "COL": 71.47,
    "GAS": 70.91,
    "HAD": 70.84,
    "HAM": 70.35,
    "HUL": 71.33,
    "LAW": 70.49,
    "LEC": 70.21,
    "LIN": 71.61,
    "NOR": 70.14,
    "OCO": 71.19,
    "PER": 70.56,
    "PIA": 70.07,
    "RUS": 70.28,
    "SAI": 70.63,
    "STR": 71.4,
    "VER": 70.0,
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
classification = predicted_classification(merged, gp_name="Dutch Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Dutch Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Dutch Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Dutch Grand Prix prediction complete!")
