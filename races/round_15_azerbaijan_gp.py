# %% [markdown]
# # 🏁 Azerbaijan Grand Prix — Prediction
# **Round 15** | Circuit: Baku City Circuit | Date: 2026-09-27

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Azerbaijan"
GP_ROUND    = 15
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.05
TEMPERATURE = 22

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 102.11,
    "ALO": 102.62,
    "ANT": 101.71,
    "BEA": 102.62,
    "BOR": 103.42,
    "BOT": 103.12,
    "COL": 103.12,
    "GAS": 102.31,
    "HAD": 102.21,
    "HAM": 101.5,
    "HUL": 102.92,
    "LAW": 101.71,
    "LEC": 101.3,
    "LIN": 103.32,
    "NOR": 101.2,
    "OCO": 102.72,
    "PER": 101.81,
    "PIA": 101.1,
    "RUS": 101.4,
    "SAI": 101.91,
    "STR": 103.02,
    "VER": 101.0,
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
classification = predicted_classification(merged, gp_name="Azerbaijan Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Azerbaijan Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Azerbaijan Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Azerbaijan Grand Prix prediction complete!")
