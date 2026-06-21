# %% [markdown]
# # 🏁 Chinese Grand Prix — Prediction
# **Round 2** | Circuit: Shanghai International | Date: 2026-03-15

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "China"
GP_ROUND    = 2
GP_YEARS    = [2024, 2025]
RAIN_PROB   = 0.15
TEMPERATURE = 18

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 94.02,
    "ALO": 94.49,
    "ANT": 93.65,
    "BEA": 94.49,
    "BOR": 95.23,
    "BOT": 94.95,
    "COL": 94.95,
    "GAS": 94.21,
    "HAD": 94.12,
    "HAM": 93.46,
    "HUL": 94.77,
    "LAW": 93.65,
    "LEC": 93.28,
    "LIN": 95.14,
    "NOR": 93.19,
    "OCO": 94.58,
    "PER": 93.74,
    "PIA": 93.09,
    "RUS": 93.37,
    "SAI": 93.84,
    "STR": 94.86,
    "VER": 93.0,
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
classification = predicted_classification(merged, gp_name="Chinese Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Chinese Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Chinese Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Chinese Grand Prix prediction complete!")
