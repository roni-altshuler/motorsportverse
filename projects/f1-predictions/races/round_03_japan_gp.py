# %% [markdown]
# # 🏁 Japanese Grand Prix — Prediction
# **Round 3** | Circuit: Suzuka | Date: 2026-03-29

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Japan"
GP_ROUND    = 3
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.2
TEMPERATURE = 16

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 88.97,
    "ALO": 89.41,
    "ANT": 88.62,
    "BEA": 89.41,
    "BOR": 90.11,
    "BOT": 89.85,
    "COL": 89.85,
    "GAS": 89.14,
    "HAD": 89.06,
    "HAM": 88.44,
    "HUL": 89.67,
    "LAW": 88.62,
    "LEC": 88.26,
    "LIN": 90.02,
    "NOR": 88.18,
    "OCO": 89.5,
    "PER": 88.7,
    "PIA": 88.09,
    "RUS": 88.35,
    "SAI": 88.79,
    "STR": 89.76,
    "VER": 88.0,
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
classification = predicted_classification(merged, gp_name="Japanese Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Japanese Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Japanese Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Japanese Grand Prix prediction complete!")
