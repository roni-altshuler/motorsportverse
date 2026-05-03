# %% [markdown]
# # 🏁 Canadian Grand Prix — Prediction
# **Round 5** | Circuit: Circuit Gilles Villeneuve | Date: 2026-05-24

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Canada"
GP_ROUND    = 5
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.25
TEMPERATURE = 20

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 72.79,
    "ALO": 73.15,
    "ANT": 72.5,
    "BEA": 73.15,
    "BOR": 73.73,
    "BOT": 73.51,
    "COL": 73.51,
    "GAS": 72.94,
    "HAD": 72.86,
    "HAM": 72.36,
    "HUL": 73.37,
    "LAW": 72.5,
    "LEC": 72.22,
    "LIN": 73.66,
    "NOR": 72.14,
    "OCO": 73.22,
    "PER": 72.58,
    "PIA": 72.07,
    "RUS": 72.29,
    "SAI": 72.65,
    "STR": 73.44,
    "VER": 72.0,
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
classification = predicted_classification(merged, gp_name="Canadian Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Canadian Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Canadian Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Canadian Grand Prix prediction complete!")
