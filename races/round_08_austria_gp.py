# %% [markdown]
# # 🏁 Austrian Grand Prix — Prediction
# **Round 8** | Circuit: Red Bull Ring | Date: 2026-06-28

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Austria"
GP_ROUND    = 8
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.3
TEMPERATURE = 22

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 65.21,
    "ALO": 65.53,
    "ANT": 64.95,
    "BEA": 65.53,
    "BOR": 66.05,
    "BOT": 65.85,
    "COL": 65.85,
    "GAS": 65.34,
    "HAD": 65.27,
    "HAM": 64.82,
    "HUL": 65.73,
    "LAW": 64.95,
    "LEC": 64.69,
    "LIN": 65.98,
    "NOR": 64.63,
    "OCO": 65.6,
    "PER": 65.02,
    "PIA": 64.56,
    "RUS": 64.76,
    "SAI": 65.08,
    "STR": 65.79,
    "VER": 64.5,
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
classification = predicted_classification(merged, gp_name="Austrian Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Austrian Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Austrian Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Austrian Grand Prix prediction complete!")
