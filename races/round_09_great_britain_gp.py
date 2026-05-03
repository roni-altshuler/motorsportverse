# %% [markdown]
# # 🏁 British Grand Prix — Prediction
# **Round 9** | Circuit: Silverstone | Date: 2026-07-05

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Great Britain"
GP_ROUND    = 9
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.35
TEMPERATURE = 18

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 87.45,
    "ALO": 87.88,
    "ANT": 87.11,
    "BEA": 87.88,
    "BOR": 88.58,
    "BOT": 88.32,
    "COL": 88.32,
    "GAS": 87.62,
    "HAD": 87.54,
    "HAM": 86.93,
    "HUL": 88.14,
    "LAW": 87.11,
    "LEC": 86.76,
    "LIN": 88.49,
    "NOR": 86.67,
    "OCO": 87.97,
    "PER": 87.19,
    "PIA": 86.59,
    "RUS": 86.85,
    "SAI": 87.28,
    "STR": 88.23,
    "VER": 86.5,
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
classification = predicted_classification(merged, gp_name="British Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="British Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="British Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ British Grand Prix prediction complete!")
