# %% [markdown]
# # 🏁 Qatar Grand Prix — Prediction
# **Round 21** | Circuit: Lusail | Date: 2026-11-29

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Qatar"
GP_ROUND    = 21
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.02
TEMPERATURE = 28

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 82.9,
    "ALO": 83.31,
    "ANT": 82.57,
    "BEA": 83.31,
    "BOR": 83.97,
    "BOT": 83.72,
    "COL": 83.72,
    "GAS": 83.07,
    "HAD": 82.98,
    "HAM": 82.41,
    "HUL": 83.56,
    "LAW": 82.57,
    "LEC": 82.25,
    "LIN": 83.89,
    "NOR": 82.16,
    "OCO": 83.39,
    "PER": 82.66,
    "PIA": 82.08,
    "RUS": 82.33,
    "SAI": 82.74,
    "STR": 83.64,
    "VER": 82.0,
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
classification = predicted_classification(merged, gp_name="Qatar Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Qatar Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Qatar Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Qatar Grand Prix prediction complete!")
