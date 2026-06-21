# %% [markdown]
# # 🏁 United States Grand Prix — Prediction
# **Round 17** | Circuit: COTA | Date: 2026-10-25

# %% — Setup
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from f1_prediction_utils import *

enable_cache(os.path.join(os.path.dirname(__file__), "..", "f1_cache"))

# %% — Configuration
GP_NAME     = "United States"
GP_ROUND    = 17
GP_YEARS    = [2023, 2024, 2025]
RAIN_PROB   = 0.1
TEMPERATURE = 24

# %% — Qualifying Estimates (auto-generated; update with real data when available)
QUALIFYING_ESTIMATES = {
    "ALB": 95.03,
    "ALO": 95.5,
    "ANT": 94.66,
    "BEA": 95.5,
    "BOR": 96.26,
    "BOT": 95.97,
    "COL": 95.97,
    "GAS": 95.22,
    "HAD": 95.13,
    "HAM": 94.47,
    "HUL": 95.79,
    "LAW": 94.66,
    "LEC": 94.28,
    "LIN": 96.16,
    "NOR": 94.19,
    "OCO": 95.6,
    "PER": 94.75,
    "PIA": 94.09,
    "RUS": 94.38,
    "SAI": 94.85,
    "STR": 95.88,
    "VER": 94.0,
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
classification = predicted_classification(merged, gp_name="United States Grand Prix")

# %% — Visualisations
generate_all_visualisations(results, merged, gp_name="United States Grand Prix")

# %% — HTML Report
generate_html_report(classification, metrics, results, merged,
                     gp_name="United States Grand Prix", circuit_key=GP_NAME,
                     gp_round=GP_ROUND)

print("\n✅ United States Grand Prix prediction complete!")
