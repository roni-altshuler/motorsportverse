# Roadmap

Forward-looking work, after the Phase 1 ML overhaul (multi-season calibration backfill, DNF probability model, race simulator CI wiring, surfaced confidence intervals) lands.

## Phase 2 — Model architecture experiments

### Hyperparameter tuning
Optuna-driven search on the Layer 1 ensemble. Persist best config to `models/hps_config.json` so training is reproducible. ~50-trial budget on val-MAE.

### Per-circuit hierarchical models
Meta-model + 22 light per-circuit sub-models. A/B test against the global model on 5 held-out rounds; ship the hierarchical variant if MAE improves ≥ 2%.

### Two-stage classifier + regressor
First predict position category (top-5 / 6-10 / 11-15 / 16-22) via classification; then refine within category via regression. Avoids the current model's tendency to over-shoot rookies and under-rate dominant cars.

### Ensemble weight logging
Log `w_gb` / `w_xgb` / `w_lstm` per round into `round_NN.json::modelConfig.ensembleWeights` so we can audit which model dominated where over the season.

### LightGBM / CatBoost benchmarking
Run the Layer 1 ensemble with LightGBM and CatBoost as alternatives to XGBoost; benchmark per-round MAE. Ship the winner if material.

## Phase 3 — Feature engineering

### Live weather API wiring
[`weather_api.py`](../weather_api.py) exists but is never called in the pipeline. Source `rain_intensity` + `temperature` from Open-Meteo at predict time; replace the hardcoded calendar values.

### SHAP ablation analysis
Per-driver prediction-error decomposition. Surface to a new `/accuracy/ablation` page showing which features moved the model most for each round's biggest misses.

### Tyre-strategy specifics
Replace the global `TyreDegFactor` with per-driver tyre-choice history and compound preference (Soft-loving aggressive drivers vs Medium-loving consistent ones).

### Safety Car Poisson
Replace the scalar `CircuitSafetyCar` (currently 0.5 avg) with a tuned Poisson rate per circuit, used by the race simulator to sample SC events.

## Phase 4 — Evaluation & infrastructure

### Leakage integration test
Full-pipeline test asserting every feature column respects `current_round` bounds (today's `tests/test_leakage.py` is unit-only).

### Calibration determinism test
Verify the calibrator produces byte-identical outputs across runs given a frozen training set.

### Race simulator determinism test
`tests/test_simulator_determinism.py` — run twice on the same grid with the same seed, assert `np.allclose(probs_run_1, probs_run_2)`.

## Phase 5 — Product

### `/value` page revival
The betting / Kelly-sizing flow exists at the Python level but the UI was removed in the 2026-05-21 redesign. Wire it back when reliable F1 odds become available (The Odds API doesn't list F1 — Pinnacle / Betfair direct ingest exists in [`odds_ingest_betfair.py`](../odds_ingest_betfair.py)).

### Driver-comparison page
`/compare?d1=VER&d2=NOR&track=Spa` — head-to-head deep dive across the season + historical record at that circuit.

### Mobile-first standings
The current standings layout works on mobile but isn't optimized for it. Compact view with sticky live cursor + horizontal scroll for the points-progression chart.

### LICENSE file
The repo currently has no `LICENSE`. MIT is the default intent (see README). Open question: license for the curated race photography manifest in `raceArt.ts`? Wikimedia content is freely licensed but the curation itself could be CC0.

## Phase 6 — Continuous learning

### Online game-theory coefficient refresh
[`models/online_game_theory.py`](../models/online_game_theory.py) already runs ridge regression on the 7 game-theory coefficients with exponential blending (α=0.30, ~2-round half-life). Add a `/accuracy/coefficients` panel surfacing how the coefficients evolve over the season.

### Auto-promotion
When [`promotion_decision.py`](../promotion_decision.py) returns "promote", CI auto-commits the candidate model artefacts as the new production stream. Today the gate exists but promotion is manual.

### Cross-season backtesting
After this season completes, run the entire 2026 pipeline retrospectively on 2024 + 2025 and report `MAE_2024 vs MAE_2025 vs MAE_2026` so we can see drift in the model's effectiveness.
