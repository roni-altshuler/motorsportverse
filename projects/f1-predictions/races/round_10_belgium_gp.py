# %% [markdown]
# # 🏁 Belgian Grand Prix — Prediction
# **Round 10** | Circuit: Spa-Francorchamps | Date: 2026-07-19

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Belgium"
GP_ROUND    = 10
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.4
TEMPERATURE = 17

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 106.15,
    "ALO": 106.68,
    "ANT": 105.73,
    "BEA": 106.68,
    "BOR": 107.52,
    "BOT": 107.2,
    "COL": 107.2,
    "GAS": 106.36,
    "HAD": 106.26,
    "HAM": 105.52,
    "HUL": 106.99,
    "LAW": 105.73,
    "LEC": 105.31,
    "LIN": 107.41,
    "NOR": 105.21,
    "OCO": 106.78,
    "PER": 105.84,
    "PIA": 105.1,
    "RUS": 105.42,
    "SAI": 105.94,
    "STR": 107.1,
    "VER": 105.0,
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
classification = predicted_classification(merged, gp_name="Belgian Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Belgian Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Belgian Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Belgian Grand Prix prediction complete!")
