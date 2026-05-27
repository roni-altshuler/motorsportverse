# Roadmap

Forward-looking work, after the Phase 1 ML overhaul (multi-season calibration backfill, DNF probability model, race simulator CI wiring, surfaced confidence intervals) lands.

## Phase 2 — Model architecture experiments

### Hyperparameter tuning  ✓ scaffolded
[`optuna_hp_search.py`](../optuna_hp_search.py) runs an Optuna study over the GB + XGB regressors and writes the winner to `models/hps_config.json`. `train_ensemble` reads that file automatically via `_load_hps_config()`. Still pending: bake an actual run into CI on a stable cadence (weekly or per-quarter) once enough forward-eval rounds exist to validate the suggested params.

### Per-circuit hierarchical models
Meta-model + 22 light per-circuit sub-models. A/B test against the global model on 5 held-out rounds; ship the hierarchical variant if MAE improves ≥ 2%.

### Two-stage classifier + regressor  ✓ scaffolded
[`models/two_stage.py::TwoStageRanker`](../models/two_stage.py) ships a fit/predict-ready classifier+regressor with a 4-bucket split (top-5 / 6-10 / 11-15 / 16-22).  Still pending: A/B benchmark vs the current single-regressor model on completed rounds, and wire-in to `export_website_data.py` if the comparison shows ≥ 2% MAE improvement.

### Ensemble weight logging  ✓ shipped
`modelConfig.ensembleWeights` is now populated in every published `round_NN.json` via [`export_website_data.py`](../export_website_data.py).

### LightGBM / CatBoost benchmarking
Run the Layer 1 ensemble with LightGBM and CatBoost as alternatives to XGBoost; benchmark per-round MAE. Ship the winner if material.

## Phase 3 — Feature engineering

### Live weather API wiring  ✓ shipped
[`weather_api.py`](../weather_api.py) `WeatherService` is invoked by `export_round_data(..., use_weather_api=True)`; [`gp_weekend.py`](../gp_weekend.py) passes the flag for both pre-race and post-quali phases. Open-Meteo provides rain probability + temperature with a 6-hour disk cache; static fallback is preserved per `_static_fallback`. The CI cron runs through this path automatically.

### SHAP ablation analysis
Per-driver prediction-error decomposition. Surface to a new `/accuracy/ablation` page showing which features moved the model most for each round's biggest misses.

### Tyre-strategy specifics
Replace the global `TyreDegFactor` with per-driver tyre-choice history and compound preference (Soft-loving aggressive drivers vs Medium-loving consistent ones).

### Safety Car Poisson
Replace the scalar `CircuitSafetyCar` (currently 0.5 avg) with a tuned Poisson rate per circuit, used by the race simulator to sample SC events.

## Phase 4 — Evaluation & infrastructure

### Leakage integration test  ✓ shipped
[`tests/test_leakage_integration.py`](../tests/test_leakage_integration.py) exercises the aggregator boundary functions (`_add_prediction_bias_features`, `_load_season_position_maps`) and asserts they refuse future-round inputs while letting prior-round data through.

### Calibration determinism test  ✓ shipped
[`tests/test_calibration.py::TestProbabilityCalibrator::test_deterministic_fit_byte_identical`](../tests/test_calibration.py) — same training set → byte-identical isotonic outputs.

### Race simulator determinism test  ✓ shipped
[`tests/test_race_simulator.py::TestDeterminism`](../tests/test_race_simulator.py) — same seed produces equal `p_win` + `mean_finish_position` dicts; different seeds diverge.

## Phase 5 — Product

### `/value` page revival
The betting / Kelly-sizing flow exists at the Python level but the UI was removed in the 2026-05-21 redesign. Wire it back when reliable F1 odds become available (The Odds API doesn't list F1 — Pinnacle / Betfair direct ingest exists in [`odds_ingest_betfair.py`](../odds_ingest_betfair.py)).

### Driver-comparison page
`/compare?d1=VER&d2=NOR&track=Spa` — head-to-head deep dive across the season + historical record at that circuit.

### Mobile-first standings
The current standings layout works on mobile but isn't optimized for it. Compact view with sticky live cursor + horizontal scroll for the points-progression chart.

### LICENSE file  ✓ shipped
[`LICENSE`](../LICENSE) (MIT) with attribution carve-outs for FastF1, Jolpica/Ergast, Wikimedia, and the headshot directory.

## Phase 6 — Continuous learning

### Online game-theory coefficient refresh
[`models/online_game_theory.py`](../models/online_game_theory.py) already runs ridge regression on the 7 game-theory coefficients with exponential blending (α=0.30, ~2-round half-life). Add a `/accuracy/coefficients` panel surfacing how the coefficients evolve over the season.

### Auto-promotion  ✓ scaffolded
`promotion_decision.py --apply` now appends "promote" recommendations to `auto_promotion_log.json`; CI passes the flag automatically. Still pending: actual registry artefact swap when a candidate stream lands. The candidate stream itself (`forward_eval_candidate/`) needs to be populated first; until then the log captures the chain of decisions for audit.

### Cross-season backtesting
After this season completes, run the entire 2026 pipeline retrospectively on 2024 + 2025 and report `MAE_2024 vs MAE_2025 vs MAE_2026` so we can see drift in the model's effectiveness.
