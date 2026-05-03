# %% [markdown]
# # 🏁 Mexico City Grand Prix — Prediction
# **Round 18** | Circuit: Autódromo Hermanos Rodríguez | Date: 2026-11-01

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "Mexico"
GP_ROUND    = 18
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.15
TEMPERATURE = 20

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 78.35,
    "ALO": 78.74,
    "ANT": 78.04,
    "BEA": 78.74,
    "BOR": 79.36,
    "BOT": 79.13,
    "COL": 79.13,
    "GAS": 78.51,
    "HAD": 78.43,
    "HAM": 77.89,
    "HUL": 78.97,
    "LAW": 78.04,
    "LEC": 77.73,
    "LIN": 79.28,
    "NOR": 77.66,
    "OCO": 78.82,
    "PER": 78.12,
    "PIA": 77.58,
    "RUS": 77.81,
    "SAI": 78.2,
    "STR": 79.05,
    "VER": 77.5,
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
classification = predicted_classification(merged, gp_name="Mexico City Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="Mexico City Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="Mexico City Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ Mexico City Grand Prix prediction complete!")
