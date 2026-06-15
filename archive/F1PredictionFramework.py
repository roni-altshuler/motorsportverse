# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
# ---

# %% [markdown]
# # 🏎️ F1 Prediction Framework — Configured Season
#
# This notebook documents the **shared prediction framework** (`f1_prediction_utils.py`)
# used to predict Formula 1 Grand Prix race results for the configured season.
#
# ---
#
# ## How to use this framework
#
# Every race-specific script (e.g. `races/round_01_australia_gp.py`) follows the
# same **6-step pattern**, all powered by functions in `f1_prediction_utils.py`:
#
# | Step | Function | Description |
# |------|----------|-------------|
# | 1 | `enable_cache()` | Set up FastF1 local cache |
# | 2 | `load_multi_year_data()` | Pull historical lap data for the circuit |
# | 3 | `aggregate_driver_stats()` → `build_grid_dataframe()` → `build_training_dataset()` | Feature engineering |
# | 4 | `get_qualifying_or_estimates()` → `apply_qualifying_data()` | Auto-fetch or estimate qualifying times |
# | 5 | `train_ensemble()` → `evaluate_models()` | Train and evaluate GB + XGBoost models |
# | 6 | `predicted_classification()` + `plot_*()` | Display results and visualisations |
#
# To **create a prediction for a new Grand Prix**, just copy any existing race notebook,
# change the GP name and qualifying estimates, and re-run.

# %% [markdown]
# ## 1. Import the Shared Module
#
# All constants, data loaders, model training, and visualisation functions live in
# `f1_prediction_utils.py`. A single wildcard import brings everything into scope.

# %%
from f1_prediction_utils import *

print("✅ f1_prediction_utils loaded successfully.")

# %% [markdown]
# ## 2. The Active F1 Grid
#
# The module contains the active configured grid: **11 teams, 22 drivers**.
#
# Key changes from 2025:
# - **Cadillac** enters as the 11th team (Sergio Pérez & Valtteri Bottas)
# - **Sauber** rebrands to **Audi**
# - **Franco Colapinto** replaces Jack Doohan at Alpine
# - **Arvid Lindblad** joins Racing Bulls
# - **Isack Hadjar** promoted to Red Bull Racing

# %%
# Display the active configured grid
grid = build_grid_dataframe()
grid[["DriverNumber", "Driver", "DriverName", "Team", "TeamPerformanceScore"]].sort_values("Team")

# %% [markdown]
# ## 3. Automatic Qualifying Data Ingestion
#
# The key scalability feature: `get_qualifying_or_estimates()` **automatically** tries to
# download real qualifying data from FastF1 after qualifying happens on Saturday.
#
# ### How it works
#
# ```python
# # In your race notebook, just call:
# quali_times = get_qualifying_or_estimates(
#     year=SEASON_YEAR,
#     grand_prix="Australia",
#     estimates=MY_ESTIMATES,   # fallback if qualifying hasn't happened
# )
# ```
#
# - **Before qualifying** → returns your hand-entered estimates
# - **After qualifying** → auto-fetches the real Q1/Q2/Q3 times from FastF1
# - **No code changes needed** — just re-run the notebook after Saturday qualifying
#
# This means you can build the prediction notebook *before* qualifying, and it
# automatically improves once real data is available.

# %% [markdown]
# ## 4. The Full Pipeline — Cheat Sheet
#
# Here is the **complete pattern** every race-specific notebook follows.
# Copy this into a new notebook and fill in the GP-specific values.
#
# ```python
# # ── 0. Import ──────────────────────────────────────────────
# from f1_prediction_utils import *
# enable_cache()
#
# # ── 1. Load historical data for this circuit ───────────────
# laps = load_multi_year_data("Australia", years=[2023, 2024, 2025])
#
# # ── 2. Feature engineering ─────────────────────────────────
# driver_stats    = aggregate_driver_stats(laps)
# grid            = build_grid_dataframe()
# merged          = build_training_dataset(grid, driver_stats)
#
# # ── 3. Qualifying data (auto-fetch or estimate) ───────────
# estimates = {"VER": 74.80, "NOR": 74.95, ...}  # your estimates
# quali = get_qualifying_or_estimates(SEASON_YEAR, "Australia", estimates)
# merged = apply_qualifying_data(merged, quali,
#                                rain_probability=0.10,
#                                temperature_c=25.0)
#
# # ── 4. Train & evaluate ───────────────────────────────────
# results = train_ensemble(merged)
# metrics = evaluate_models(results)
# merged  = results["merged"]
#
# # ── 5. Results & plots ────────────────────────────────────
# classification = predicted_classification(merged, "Australian Grand Prix")
# plot_feature_importance(results)
# plot_predicted_laptimes(classification, "Australian Grand Prix")
# plot_team_vs_pace(merged, "Australian Grand Prix")
# plot_pace_vs_predicted(merged, "Australian Grand Prix")
# ```

# %% [markdown]
# ## 5. Available Constants Reference
#
# All constants are defined in `f1_prediction_utils.py` and can be accessed directly:
#
# | Constant | Type | Description |
# |----------|------|-------------|
# | `DRIVER_TEAM` | `dict[str, str]` | Driver code → team name |
# | `DRIVER_FULL_NAMES` | `dict[str, str]` | Driver code → full name |
# | `DRIVER_NUMBERS` | `dict[str, int]` | Driver code → car number |
# | `CONSTRUCTOR_POINTS_2025` | `dict[str, int]` | Team → 2025 championship points |
# | `TEAM_PERFORMANCE_SCORE` | `dict[str, float]` | Team → normalised [0, 1] score |
# | `WET_PERFORMANCE` | `dict[str, float]` | Driver code → wet-weather factor |
# | `CLEAN_AIR_PACE` | `dict[str, float]` | Driver code → avg race pace (s) |
# | `CALENDAR` | `dict[int, dict]` | Round → race metadata |
# | `TEAM_COLOURS` | `dict[str, str]` | Team → hex colour code |
# | `DEFAULT_FEATURE_COLS` | `list[str]` | Default model features |

# %%
# Quick peek at the active calendar (rounds added so far)
import pandas as pd
cal_df = pd.DataFrame(CALENDAR).T
cal_df.index.name = "Round"
cal_df

# %% [markdown]
# ## 6. Running a Race Prediction
#
# All rounds in the active season have pre-generated prediction scripts in the `races/` folder.
#
# ```bash
# python races/round_01_australia_gp.py
# python races/round_02_china_gp.py
# python races/round_08_monaco_gp.py
# ```
#
# Each script automatically:
# - Generates qualifying estimates based on circuit characteristics
# - Loads historical data, builds the enriched feature set
# - Trains the ensemble model with prediction calibration
# - Produces hierarchical visualisations and an HTML race report
#
# To regenerate all 24 race scripts (e.g. after updating the framework):
# ```bash
# python create_season_races.py
# ```
#
# ---
#
# ### Scalability Checklist
#
# - ✅ All 22 drivers and 11 teams defined **once** in `f1_prediction_utils.py`
# - ✅ Model training, evaluation, and visualisation are **reusable functions**
# - ✅ Qualifying data **auto-fetches** after the session — no manual editing needed
# - ✅ **24 race scripts** pre-generated in `races/` — just run them
# - ✅ **Current-season form** — earlier race results feed into later predictions
# - ✅ Update the grid mid-season? Edit `f1_prediction_utils.py` once, re-run `create_season_races.py`
