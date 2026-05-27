# ML pipeline

Detailed walkthrough of how each prediction is produced, including the recent Phase 1 overhaul (multi-season calibration backfill, DNF probability model, race simulator CI wiring, surfaced confidence intervals).

## Training data

**Source:** `data/history.duckdb`, a local DuckDB populated by two backfill streams:

1. **Tier 1 — FastF1** ([`backfill_history.py`](../backfill_history.py)) — rich lap-by-lap telemetry; rate-limited to ~500 requests/hour by the FastF1 cache, so typically tops out at 24-30 rounds per run. The DB is idempotent (PK on `(season, round, driver)`).

2. **Tier 2 — Ergast / Jolpica-compatible** ([`ergast_backfill.py`](../ergast_backfill.py)) — historical race results back to 1950; no rate cap; faster broad coverage.

Both backfills are scheduled in [`.github/workflows/backfill_history.yml`](../.github/workflows/backfill_history.yml) (nightly cron at 03:00 UTC). The DB is gitignored at the project root but committed via `git add -f` from the workflow.

## Feature engineering

Catalogue lives in [`f1_prediction_utils.py::build_training_dataset`](../f1_prediction_utils.py) (38 features).

| Category | Features |
|---|---|
| Driver | Adjusted qualifying time, prior-round form, season starts, experience, Elo |
| Team | Team form, season form, team-change adjustment |
| Circuit | Overtaking factor, Safety Car probability, grip penalty, sprint flag |
| Strategy | Expected pit-stop count, pit-time-loss, tyre degradation factor |
| Conditions | Rain probability, track temperature, air temperature |
| Game theory | 7 coefficients tuned by ridge regression (sentinel round 98) |

### Leakage discipline
[`leakage.py`](../leakage.py) exports `assert_prior_only(rounds_map, current_round, label)` and `assert_seasons_prior_only(...)`. Every aggregator that touches multi-round history must filter to rounds strictly less than `current_round`. The assertion is wired at the boundary in [`f1_prediction_utils.py::build_training_dataset`](../f1_prediction_utils.py) and inside `_load_season_position_maps`.

**Rule when adding a new feature**: plumb `current_round` through and assert at the boundary — don't trust your own filter.

## Training methodology

**Layer 1** ([`f1_prediction_utils.py::train_ensemble`](../f1_prediction_utils.py)): per-race fit on 22 drivers. The `train_test_split` splits **drivers** within a race, not rounds — this is not a forward-time evaluation. Returns same-race metrics for sanity-checking ensemble weighting only. The real validation surface is [`forward_eval.py`](../forward_eval.py).

**Ensemble weighting**: Gradient Boosting + XGBoost weights computed per race from inverse-MAE on held-out drivers. LSTM weight clamped to `[0.10, 0.18]` when active.

**Hyperparameters**: hardcoded today (`n_estimators=200/250`, `learning_rate=0.05`, `max_depth=3`). Optuna search is on the roadmap ([docs/ROADMAP.md](ROADMAP.md)).

## Probability layer

**Plackett-Luce sampler** via Gumbel-max trick, 5000 Monte Carlo samples, deterministic seed (`np.random.default_rng(seed=42)`). Outputs:

```
classification[i] = {
  winProbability,
  podiumProbability,
  top6Probability,
  top10Probability,
  predictedTime,
  predictionIntervalLow,   // 5th percentile, 90% bootstrap CI
  predictionIntervalHigh,  // 95th percentile
  dnfProbability,          // Phase 1
  simulatorWinProbability  // when --use-race-simulator
}
```

Plus a full per-driver head-to-head matrix.

## Calibration

[`models/calibration.py`](../models/calibration.py).

- `ProbabilityCalibrator.fit_from_history(...)` — isotonic regression on `(predicted_p, observed_outcome)` pairs from `data/history.duckdb`.
- `StratifiedProbabilityCalibrator` — extends with per-(market, stratum) fits and a global fallback.

**Honest gate**: `export_probabilities.py` writes `calibration.applied = false` until the history DB contains ≥ `--min-completed-rounds` distinct `(season, round)` tuples (default 3). When `applied=false`, raw Plackett-Luce numbers are published and the dashboard surfaces a disclaimer. **Never claim calibration is applied without verifying the gate trips.**

## Race simulator (Layer 3)

[`models/race_pace.py`](../models/race_pace.py) + [`models/race_simulator.py`](../models/race_simulator.py).

- Per-lap GB + XGB ensemble on lap-by-lap telemetry; 16-feature catalogue (driver/team/circuit ids, lap_number, lap_progress, track_position, tyre_compound_code, tyre_age_laps, gaps to front/behind, SC/VSC/yellow flags, temps, rain_intensity).
- Simulator iterates `predict_lap_times` per driver per lap, maintains running gaps + positions, samples pit-stop laps, injects SC events from a Poisson process.
- Default 2000 Monte Carlo samples.
- Trained offline via [`train_race_pace.py`](../train_race_pace.py); persisted under `models/registry/<season>_round_99/` (sentinel round 99) with `metadata.kind=="race-pace"`.

**Phase 1 wiring**: `--use-race-simulator` is now passed from [`gp_weekend.py`](../gp_weekend.py) (CI entry point) and the workflow pre-steps `train_race_pace.py --seasons 2018-2025` to ensure the ensemble is registered before the simulator runs.

## DNF probability model (Phase 1)

[`models/dnf.py`](../models/dnf.py). Sentinel registry round 97.

- Logistic regression (`class_weight="balanced"`) trained on historical mechanical/strategy DNFs.
- Target: `position > 20 OR retired` from the historical race archive.
- Features: driver, team, prior-5-race DNF rate, qualifying gap, weather (rain probability).
- Output: per-driver `p_dnf` for the upcoming race.

**Integration points**:
1. Spliced into `probabilities/round_NN.json::classification[*].dnfProbability` (optional field).
2. Race simulator samples `Bernoulli(p_dnf)` per driver per simulation; DNF'd drivers are excluded from position updates from their DNF lap onward.

## Confidence intervals

[`models/intervals.py::bootstrap_prediction_intervals`](../models/intervals.py) — 20-replica bootstrap of the Gradient Boosting regressor over (X_train, y_train) at lighter `n_estimators=80` per replica. 90% CI = `[5th percentile, 95th percentile]`.

Outputs ship to round JSON as `predictedTime` + `predictionIntervalLow` + `predictionIntervalHigh`. The Phase 1 UI overhaul surfaces these as `<ErrorBar>` whiskers on the lap-time chart.

## Determinism

| Component | Seed |
|---|---|
| Plackett-Luce sampler | `np.random.default_rng(seed=42)` |
| Race simulator | `DEFAULT_SEED = 42` |
| DNF model | `random_state=42` on LogisticRegression |
| Bootstrap intervals | `random_state=42` per replica |

Identical inputs produce identical outputs across runs. Verify via `pytest tests/test_simulator_determinism.py` (see [docs/MODEL_EVALUATION.md](MODEL_EVALUATION.md)).

## Inference pipeline

End-to-end for a single round:

```bash
# 1. Predict pace + probabilities + simulator probabilities
python export_website_data.py --round 5 --fastf1 --advanced --use-race-simulator

# 2. Layer 2 probabilities + calibration summary
python export_probabilities.py --rounds 5

# 3. Forward-time evaluation (after the race)
python forward_eval.py --season 2026 --per-round-dir website/public/data/forward_eval --allow-empty

# 4. Drift + promotion (continuous learning)
python drift_report.py --season 2026 --allow-empty
python promotion_decision.py --season 2026 --allow-empty
```

All wired into [`.github/workflows/update_predictions.yml`](../.github/workflows/update_predictions.yml).
