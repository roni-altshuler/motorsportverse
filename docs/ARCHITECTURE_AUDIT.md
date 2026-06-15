# Architecture Audit — Prediction System

Snapshot date: 2026-05-28. Source of truth: the code in this repo as of commit `fcc80fa` (the commit before this audit landed).

This document answers the question "what does our prediction system actually do today?" — separately from what it *could* do. Each section pairs a claim with the file/lines that back it up, so the next reviewer can verify rather than trust.

---

## 1. Current architecture (TL;DR)

We run a **three-layer hybrid system** with per-race retraining and a small set of explicit blending policies. There is no single monolithic model.

| Layer | What it does | Where it lives | Per-race or global? |
|------|---------------|----------------|---------------------|
| L1 — Lap-time regressor | Predicts each driver's qualifying-equivalent lap time | [`f1_prediction_utils.py::train_ensemble`](../f1_prediction_utils.py) | Per-race (trained fresh per round) |
| L2 — Probability layer | Maps L1 ranking → win/podium/top-6/top-10 probabilities + isotonic calibration | [`models/calibration.py`](../models/calibration.py) + [`export_probabilities.py`](../export_probabilities.py) | Per-race sampling; calibrator trained on multi-season history |
| L3 — Per-lap race simulator (opt-in) | Lap-by-lap Monte Carlo with pit stops + SC events | [`models/race_pace.py`](../models/race_pace.py) + [`models/race_simulator.py`](../models/race_simulator.py) | Single trained ensemble (sentinel round 99) re-used across all races |

The pipeline also carries optional bolted-on heads (DNF, championship simulator, hybrid-blend policy, per-circuit hierarchical head) that are **scaffolded and tested but not all wired into the live pipeline** — flagged below.

---

## 2. Layer 1 — the per-race ensemble

The target is `AdjustedQualiTime`, not race finishing position. Training happens fresh for every round.

**Ensemble members** (file: [f1_prediction_utils.py:1444](../f1_prediction_utils.py)):
- Gradient Boosting regressor (sklearn)
- XGBoost regressor
- LSTM (optional; only when post-quali phase ships richer features)

**Weighting**:
- Inverse-MAE weighting on the held-out test split — better-performing model gets more weight per round.
- When LSTM is active, `lstm_weight` is clipped to [0.10, 0.18] and the GB/XGB share is renormalised.
- Final weights are written to `round_NN.json::modelConfig.ensembleWeights` (shipped 2026-05-27).

**Train/test split**: `train_test_split(test_size=0.2, random_state=42)` over the 22-driver per-race frame. This is *driver-splitting* inside a single race — **not** forward-time validation. The true forward-time signal is `forward_eval.py`, not the inline R² printed during training.

**Per-circuit specialisation**:
- Today: **none in the live pipeline**. A `PerCircuitHierarchicalModel` exists in [`models/per_circuit.py`](../models/per_circuit.py) with 6 passing tests, but it is **not wired into `export_round_data`**. The roadmap calls for A/B-benchmarking before wiring. → Action item.

---

## 3. Layer 2 — probabilities + calibration

After L1 emits per-driver lap-time predictions:

1. **Plackett-Luce sampling** with the Gumbel-max trick — 5,000 MC samples, `np.random.default_rng(seed=42)`. Produces `p_win`, `p_podium`, `p_top6`, `p_top10` per driver plus an H2H matrix.
2. **Isotonic calibration** via [`StratifiedProbabilityCalibrator`](../models/calibration.py) — per-(market, stratum) fits with a global fallback. Trained on `data/history.duckdb` which currently holds 2,575 race-rounds (1950–1953 ergast snapshot + 2018–2025 backfill).
3. **`calibration.applied` gate**: only flips to `true` once the history DB has ≥ 3 distinct (season, round) tuples. Confirmed live for the 2026 rounds emitted post-backfill.

Bootstrap 90% prediction intervals on per-driver predicted lap time are computed in [`models/intervals.py`](../models/intervals.py) and exported as `predictionIntervalLow` / `predictionIntervalHigh` on each classification entry — rendered as error-bar whiskers on the predicted-pace chart.

---

## 4. Layer 3 — opt-in race simulator

Wired through `--use-race-simulator`. When active:
- Loads the registered race-pace ensemble (sentinel round 99 in the model registry)
- Iterates `predict_lap_times` per driver per lap (16-feature catalogue: driver/team/circuit ids, lap_number, lap_progress, track_position, tyre_compound_code, tyre_age_laps, gap_to_car_ahead/behind, sc/vsc/yellow flags, air/track temp, rain_intensity)
- Maintains running gaps + positions, samples pit-stop laps, injects safety-car events from a Poisson process
- 2,000 MC samples by default
- Output: `simulatorWinProbability`, `simulatorPodiumProbability`, `simulatorTop6Probability`, `simulatorTop10Probability`, `simulatorMeanFinish` per driver + a `modelConfig.raceSimulator` block

Pre-step required: `train_race_pace.py` must be run at least once to populate the registry. CI does this automatically.

**Status check**: simulator silently no-ops when the registry has no race-pace ensemble. Worth tracking the `modelConfig.raceSimulator.applied` flag round-by-round to confirm CI's pre-step is succeeding.

---

## 5. Continuous-learning loop

The full loop runs in [`.github/workflows/update_predictions.yml`](../.github/workflows/update_predictions.yml):

1. **`gp_weekend.py`** — phase-aware runner; emits `predictionPhase ∈ {"preview", "post-quali", "post-race"}` on the round JSON. Pre-quali predictions are intentionally hidden in the UI (shipped 2026-05-27).
2. **`forward_eval.py`** — per-round MAE / Spearman / NDCG@5 / podium-hit / winner-hit + a `last_race_winner` baseline. Outputs `forward_eval/round_NN.json`.
3. **`drift_report.py`** — PSI per feature + rolling-Brier trend. Severity bands: PSI 0.10/0.25, Brier 5%/15% regression.
4. **`promotion_decision.py`** — guarded production/candidate comparison. ≥5 overlapping rounds, ≥2% mean improvement, no per-round 20%+ regression. CI now passes `--apply` which appends "promote" decisions to `auto_promotion_log.json`.
5. **`championship_simulator.py`** — Monte Carlo championship-outlook simulator (WDC + WCC) with skill softening (temperature 0.65) and per-race DNF sampling.

---

## 6. Hybrid-blend policy

The product brief asked for "dynamic weighting of track-specific historical performance vs current weekend signals." [`models/hybrid_blend.py`](../models/hybrid_blend.py) ships an explicit policy:

| Phase | Circuit type | Weight (historical, weekend) |
|-------|--------------|------------------------------|
| Preview (pre-quali) | any | (1.00, 0.00) — no weekend data exists |
| Post-quali | Quali-dominant (Monaco, Hungary, Singapore) | (0.20, 0.80) |
| Post-quali | Specialist circuits (Brazil, Spa, Suzuka) | (0.45, 0.55) |
| Post-quali | High-variance (Bahrain, Saudi, Miami, Canada) | (0.40, 0.60) |
| Post-quali | Default | (0.35, 0.65) |
| Post-race | any | (0.20, 0.80) — race signal dominates |

13 tests cover the policy. **Status**: the policy module is callable but the production pipeline does not yet route through it. → Action item.

---

## 7. What gets persisted

| Artefact | Location | Refreshed |
|----------|----------|-----------|
| Round predictions + classification | `website/public/data/rounds/round_NN.json` | Every pipeline run |
| Win/podium/top-k + DNF | `website/public/data/probabilities/round_NN.json` | Every pipeline run |
| Calibration summary | `website/public/data/probabilities/calibration_summary.json` | Every pipeline run |
| Per-round forward-eval | `website/public/data/forward_eval/round_NN.json` | Post-race |
| Drift / health | `website/public/data/model_health.json` | Every pipeline run |
| Promotion decision | `website/public/data/promotion_status.json` | Every pipeline run |
| Championship forecast | `website/public/data/championship_forecast.json` | Every pipeline run |
| Historical backtest (new) | `website/public/data/historical_backtest/*.json` | On-demand via `historical_backtest.py` |
| Model registry | `models/registry/<season>_round_<NN>/` | Per round; binaries gitignored, `metadata.json` committed |

---

## 8. Known gaps (action items)

| # | Item | File / area |
|---|------|-------------|
| 1 | Per-circuit hierarchical model is built + tested but not in the live pipeline | [`models/per_circuit.py`](../models/per_circuit.py) — needs wiring into `export_round_data` after an A/B benchmark |
| 2 | Hybrid blend policy is built + tested but not in the live pipeline | [`models/hybrid_blend.py`](../models/hybrid_blend.py) — needs wiring into the L1 → L2 hand-off |
| 3 | Two-stage classifier+regressor scaffolded only | [`models/two_stage.py`](../models/two_stage.py) — same status |
| 4 | Optuna search hasn't been run yet | [`optuna_hp_search.py`](../optuna_hp_search.py) — needs a one-off run to populate `models/hps_config.json` |
| 5 | LightGBM/CatBoost benchmark not yet run | [`benchmark_gbm_libraries.py`](../benchmark_gbm_libraries.py) — needs a one-off run |
| 6 | Cross-season backtest used qualifying-pace baseline, not full pipeline retrospective | [`historical_backtest.py`](../historical_backtest.py) — a true retrospective requires re-training per-round on 2024 data with strict prior-only filtering |
| 7 | SHAP ablation page UI not built | [`shap_ablation.py`](../shap_ablation.py) writes the data; `/accuracy/ablation` page is the missing surface |
| 8 | No standalone "calibration on the road" surface | The Accuracy page redesign shipped 2026-05-28 adds this |

---

## 9. Where the prediction error actually comes from (2026 rounds 1-5)

Three sources dominate the residuals so far:

1. **Mechanical DNFs** — NOR R5 P1→P18 was outside the regressor's modelling space. The DNF model now captures this signal pre-race; effectiveness needs another 4-5 rounds of evidence.
2. **Rookie variance** — the qualifying-time model anchors on circuit-specific history that rookies don't have. Mitigated partly by the `DriverExperience` and `RookieFactor` features but still a residual source.
3. **Strategy divergence** — pit-stop calls and SC timing produce outcomes outside what a lap-time regressor can express. The Layer 3 simulator is the mitigation; needs the race-pace ensemble to be re-trained on 2025 telemetry to be fully effective.

---

## 10. Recommendation

The architecture itself is fine — the three-layer split is the right call. The wins from here come from (in priority order):

1. **Wire the existing scaffolded components into the live pipeline** (hybrid blend, per-circuit, two-stage). All three are built, tested, and idle.
2. **Run the Optuna sweep + LightGBM benchmark.** Both scripts are ready; each takes one offline run.
3. **Retrain the race-pace ensemble** with 2025 telemetry so the L3 simulator is actually doing useful work.
4. **Build the SHAP ablation surface** so future audits are grounded in feature-level evidence rather than narrative.

The accuracy page redesign that ships alongside this audit gives users (and us) a continuous signal on where the model is winning vs losing — round-over-round, per-circuit, per-driver, and calibrated-vs-actual.

---

## 11. Phase 10 production freeze (2026-05-28)

After Phases 5–9 explored regime routing, probabilistic fusion, mixture-of-experts gating, and dynamic telemetry features, the strongest variant on every honest backtest is `regime_routed_with_weekend_static`: the Phase-5 regime router on top of an elite head trained over the 7-column Phase-7 static weekend feature set. The freeze decision and its enforcement live in code:

* **Production model facade** — [`models/production_model.py`](../models/production_model.py) wraps the variant as a stable callable. Its `predict_for_round(frame, prior)` returns a frozen `ProductionPrediction` schema with `model_version` and `model_variant` baked in.
* **Feature flag** — `F1_PRODUCTION_MODEL_ENABLED` (env var). Defaults to `"0"` (off). Flip to `"1"` to route a production caller through the freeze. The flag is required reading for `gp_weekend.py` / `export_website_data.py` if either ever wires this in.
* **Canonical feature set** — [`models/weekend_features.py`](../models/weekend_features.py) `WEEKEND_FEATURE_COLUMNS` is now the 7-column Phase 7 set. The 3 Phase-8 dynamic curves (`fp2_deg_slope`, `q_vs_fp2_pace_delta`, `intra_stint_drift`) were demoted to `ARCHIVED_DYNAMIC_COLUMNS` after combined importance dropped from 4.1% (2-season) to 1.6% (3-season) — the wrong direction under added data. They are preserved in the parquet on disk for reproducibility but are NOT in any production training path. Research benchmarks can opt in via `WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH`.
* **Default benchmark lineup** — [`benchmark_models.py`](../benchmark_models.py) `--variants` default is now `baseline,elite_head_plus_hybrid,regime_routed_with_weekend_static`. The experimental variants (MoE, Phase 8 full, per_circuit/hybrid_blend, temporally_robust, regime_routed_three_layer) are accessible via `--include-research` so they remain reproducible without polluting the default report.

**Versioning protocol.** `PRODUCTION_MODEL_VERSION = "2026.07.phase7-static"`. Bumping this version requires:

1. A freeze benchmark (`python src/benchmark_models.py run --seasons 2024 2025`) showing the new candidate beats `regime_routed_with_weekend_static` on aggregate winner-hit by at least +1pp with no per-season regression beyond 1pp.
2. Updating this section of the audit.

**Data infrastructure.** [`backfill_2018_2022.py`](../backfill_2018_2022.py) lands the FastF1 backfill into `data/history.duckdb` (TLA driver codes; idempotent INSERT OR REPLACE). 2022 already landed (22 rounds, 439 complete observations). 2018-2021 are the remaining one-command runs once the FastF1 cache covers those rounds. The expected payoff is direct: Phase 9 showed ~+6pp winner-hit per added season on the existing static model — five more seasons could push the aggregate to ~40-50% winner-hit if scaling is even half-linear.

**What was demoted to research.** MoE gate, three-layer probabilistic fusion, regime-routed-three-layer (non-static), temporally-robust probabilistic, per-circuit hierarchical, hybrid blend, two-stage classifier, and the Phase 8 dynamic features. All preserved in-tree, but none are on the production path. The fixed lesson: with `n=48-92` training rounds, additional architectural complexity consistently saturates or regresses; the highest-ROI bet is data depth on the existing static model.
