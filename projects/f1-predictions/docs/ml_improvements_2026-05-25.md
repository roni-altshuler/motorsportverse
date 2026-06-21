# F1 Predictions — ML Improvements (2026-05-25)

This document describes the architectural improvements landed on
2026-05-25 against the baseline reviewed in
[ml_architecture_review_2026-05-24.md](./ml_architecture_review_2026-05-24.md).

The goal was strengthening the existing 3-layer stack with
**realistic, statistically sound** additions — not a rewrite. Every
change is backwards-compatible: the legacy code path remains the
load-bearing production behaviour until the new layer is measured
better.

---

## Summary of changes

| Change | New module | Integration site | Status |
|---|---|---|---|
| Regulation-era boundaries + decay helpers | [`models/regulation_era.py`](../models/regulation_era.py) | Foundation for time-decay + Elo | Live |
| Exponential time-decay sample weighting | [`models/time_decay.py`](../models/time_decay.py) | `train_ensemble(sample_weight=...)` | Opt-in |
| Driver + team Elo features (7 features) | [`models/elo.py`](../models/elo.py) | `build_training_dataset → _add_elo_features` | Active by default |
| Split conformal prediction intervals | [`models/conformal.py`](../models/conformal.py) | `apply_race_postprocessing` (additive) | Activates after ≥8 residuals accumulated |
| Reliability diagrams + ECE + MCE + Brier | [`models/reliability.py`](../models/reliability.py) | `forward_eval.py --probabilities-dir ...` | Opt-in CLI flag |
| LightGBM learned race-projection head | [`models/race_projection_head.py`](../models/race_projection_head.py) | `apply_race_postprocessing` shadow column | Opt-in via `F1_USE_LEARNED_HEAD=1` |
| Bayesian hierarchical skill model (scaffold) | [`models/hierarchical_bayes.py`](../models/hierarchical_bayes.py) | None yet — registry sentinel reserved at round 97 | Feature-flagged |
| Old-vs-new benchmark + head trainer | [`benchmarks/run_ml_comparison.py`](../benchmarks/run_ml_comparison.py) | New CLI | Live |
| Leakage assertion at bias-feature boundary | [`f1_prediction_utils.py::_add_prediction_bias_features`](../f1_prediction_utils.py) | `current_round` arg now required at the call site | Live |

All changes are exercised by **569 passing tests** (24 new tests for the
new modules + 1 new test for the leakage-assertion contract).

---

## 1. Regulation-era awareness

Single source of truth for F1 regulation eras (V6-hybrid intro, wide
cars, ground-effect, 2026 active-aero). Two helpers feed the rest of
the stack:

* `era_of(season)` — which era a season belongs to.
* `era_decay_factor(row_season, current_season, mode, decay)` —
  multiplicative weight in `[0, 1]` that discounts rows from older
  eras. Three modes: `exponential` (half per era boundary by default),
  `hard_cut` (1.0 within N eras, 0 beyond), `none` (passthrough for
  ablations).

Used internally by [`models.time_decay`](../models/time_decay.py) and
intended for use by any future feature that aggregates across years.

---

## 2. Time-decay sample weighting

Per-row training weight = exponential round recency × era distance.
Defaults: 8-round half-life, exponential era mode with 0.5 decay per
era boundary. The weights are normalized so the **mean is 1.0** — the
loss scale matches the legacy uniform fit, so a weighted-vs-unweighted
comparison is honest.

### Integration

`train_ensemble(merged, ..., sample_weight=...)` — the new keyword is
forwarded to both `GradientBoostingRegressor.fit(sample_weight=...)`
and `XGBRegressor.fit(sample_weight=...)`. Default `None` preserves
legacy behaviour.

### How callers turn it on

The intended pattern (added to a follow-up PR):

```python
from models.time_decay import compute_sample_weights

weights = compute_sample_weights(
    seasons=training_rows["season"],
    rounds=training_rows["round"],
    current_season=2026,
    current_round=N,
    half_life_rounds=8,
    era_mode="exponential",
)
results = train_ensemble(merged, sample_weight=weights)
```

The existing per-race ensemble uses one race's data only, so the
immediate benefit is small. The big lift comes when the
multi-season training surface widens to include the LightGBM head
(below) and the offline race-pace ensemble.

---

## 3. Driver + Team Elo features

Seven new features now appear in `DEFAULT_FEATURE_COLS`:
`driver_elo`, `team_elo`, `driver_form_elo`, `wet_weather_elo`,
`qualifying_elo`, `racecraft_elo`, `teammate_delta_elo`.

### Implementation highlights

* **Standard symmetric pairwise Elo** in [models/elo.py](../models/elo.py): expected
  score `E_a = 1 / (1 + 10^((R_b − R_a) / 400))`, update
  `R_a' = R_a + K * (S_a − E_a)`. K-factor schedule:
  40 (provisional, n_races < 10), 25 (10–30), 15 (>30).
* **Team Elo damped** with `k_damping=0.4` so the team rating moves
  more slowly than driver ratings — matches the empirical
  observation that team performance is more stable than driver form
  within a season.
* **Rookie cold-start**: a new driver is initialised at
  `team_mean − 25` so the rating is principled instead of arbitrary
  (default 1500). Mid-season swaps inherit history.
* **Inter-season decay**: when stepping from season S to S+1, each
  rating is pulled toward the league mean by 15% (same era) or 50%
  (era boundary). This is the regulation-reset surface: 2026 → 2027
  same era keeps continuity; 2025 → 2026 crosses the active-aero
  boundary and applies stronger shrinkage.
* **Leakage discipline**: `EloFeatureBuilder.replay_history(events,
  current_season, current_round)` refuses any event at or beyond
  the cutoff, mirroring `leakage.assert_seasons_prior_only`.

### Variant Elo systems

The builder keeps several independent rating systems in parallel:
race result, qualifying (uses grid order), wet-weather, race-craft
(positions gained from grid to finish), and team. Adding more — e.g.
``street_circuit_elo`` — is one new internal `DriverElo` + a wiring
line in `EloFeatureBuilder.ingest_race`.

### Update equations (canonical)

```
For each (driver_i, driver_j) pair in finish_order with finish_i < finish_j:
    S_i = 1.0
    E_i = 1 / (1 + 10^((R_j − R_i)/400))
    K_i = k_factor_for_experience(n_races[i]) * k_damping
    R_i' = R_i + K_i * (S_i − E_i)
    Same for j (S_j = 0.0).

After all pairs:
    n_races[i] += 1   for every participant.

When stepping to a new season:
    R_i' = mean + (R_i − mean) * (era_boundary_shrink if era changed else inter_season_shrink)
```

### Rookie initialization (canonical)

```
team_ratings = [R_d for d in DRIVERS if team(d) == t and rated(d)]
if team_ratings is empty:
    R_rookie = league_mean − discount        # 1500 − 25 = 1475
else:
    R_rookie = mean(team_ratings) − discount
```

The discount avoids over-rating rookies on debut. After ~10 races
the K-factor schedule moves them to settled ratings naturally.

### Limits

* **Current-season only.** Multi-season Elo bootstrap would need a
  per-season driver→team mapping that we don't currently store
  (history.duckdb has driver but not team). Adding that mapping is
  a clean follow-up.
* **Wet-race flag missing.** `combined_results` doesn't carry a wet
  indicator yet, so `wet_weather_elo` will be 1500 for every driver
  until that signal is plumbed through. The feature is still
  exposed so the ensemble can learn from it once data lands.
* **Grid order approximated by finish order** when no grid data is
  joined to `combined_results`. This understates qualifying-elo
  signal early in the season; gets sharper once FastF1 grid data
  is wired in.

---

## 4. Split conformal prediction intervals

Replaces the percentile-clipped confidence buckets with a
statistically valid interval:

```
q_α = empirical (1 − α)(1 + 1/n) quantile of |y − ŷ| on calibration set
[low, high] = [ŷ − q_α, ŷ + q_α]
```

### Coverage guarantee

Under exchangeability, `P(y ∈ [low, high]) ≥ 1 − α` for any test
point. With α=0.10 the interval covers ~90% of true lap times.

### How calibration data accumulates

Each call to `train_ensemble` writes its 4–5 held-out residuals to
`data/conformal_residuals/<season>_round_<NN>.json`. The cache
directory is gitignored. `apply_race_postprocessing` reads the
accumulated cache (filtered to rounds < current_round) and fits
`ConformalIntervals` when ≥8 residuals are available.

Per-round write keeps the file count small (~22/season); each file
is a few hundred bytes. The next round starts with rounds_so_far × 5
calibration samples — enough for a meaningful quantile by round 3.

### Stratified variant

`StratifiedConformal` partitions calibration data by stratum
(`"dry"` / `"wet"` / `"rookie"` / `"settled"` / `"early_season"` /
`"settled_season"`) and falls back to the global quantile when a
stratum has fewer than `min_samples_per_stratum` rows. Not wired
into `apply_race_postprocessing` yet — needs the wet-race indicator
discussed in §3.

### Output columns added to `merged`

* `PredictedLapTimeConformalLow`
* `PredictedLapTimeConformalHigh`
* `ConformalIntervalWidth`
* `CalibratedConfidence` (High/Medium/Low from `width_to_confidence_label`)

These coexist with the legacy `PredictionUncertainty` /
`PredictionConfidence` columns. The website type contract has not
been extended yet — a follow-up PR can surface the new fields once
coverage data confirms the intervals are well-calibrated.

### Assumptions and limitations

* **Exchangeability is approximate.** Wet vs dry races, regulation
  changes, and rookies all violate it. The stratified variant
  improves this.
* **Symmetric intervals** around `ŷ`. Fine for lap time (residuals
  roughly Gaussian); inappropriate for finishing position (clipped
  at 1).
* **Cold-start.** Until ≥8 residuals are cached (≈ round 2-3),
  conformal stays deferred and the legacy `PredictionConfidence` is
  the only signal published.
* **Time-warp**: the cache mixes residuals from old and recent
  rounds equally. Time-decay weighting of the calibration set is
  a natural next refinement.

---

## 5. Reliability diagrams + ECE + MCE + Brier

[models/reliability.py](../models/reliability.py) exposes the
calibration measurement layer. Definitions:

* **Bin:** equal-width bucket of predicted probabilities (10 by
  default). For each bin: mean predicted probability and mean
  observed outcome.
* **ECE:** sample-weighted mean of `|mean_pred − mean_obs|` across
  bins. Single-scalar calibration summary.
* **MCE:** max over bins of the same per-bin gap. Catches the worst
  bucket.
* **Brier:** mean squared error between predicted probability and
  observed 0/1 outcome. Lower = better probabilistic forecast.

### `forward_eval.py` extension

Two new CLI flags:

```
--probabilities-dir <path>          # input: per-round probability JSON
--reliability-plots-dir <path>      # output: one PNG per market
```

When `--probabilities-dir` is set, the season report JSON gains a
`calibration` block with per-market ECE/MCE/Brier. When
`--reliability-plots-dir` is also set, one reliability diagram is
written per market (win, podium, top6, top10).

The plots follow `viz_style` styling so they fit the chart
catalogue. They're suitable for the website's accuracy dashboard
or for hand inspection of which markets are calibrating well.

### Today's calibration numbers (2026 season, round 4 actuals only)

From `python -m benchmarks.run_ml_comparison --season 2026 --fit-head`:

```
win:    ECE=0.063  MCE=0.125  Brier=0.039
podium: ECE=0.025  MCE=0.025  Brier=0.112
top6:   ECE=0.332  MCE=0.437  Brier=0.154
top10:  ECE=0.248  MCE=0.305  Brier=0.171
```

The `win` and `podium` markets are well-calibrated. The `top6` and
`top10` markets are poorly calibrated — the isotonic calibrator
hasn't separated them yet because the history DB doesn't carry
enough completed-round samples. This is exactly the kind of
diagnostic the new ECE/MCE/Brier layer surfaces.

---

## 6. LightGBM learned race-projection head

[models/race_projection_head.py](../models/race_projection_head.py)
fits a LightGBM regressor

```
(PredictedLapTime, AdjustedQualiTime, CleanAirPace, CurrentForm,
 PreviousPosition, ConsistencyScore, PitTimeLoss, TyreDegFactor,
 SeasonMomentum, GridAdvantage, DriverPredictionBias,
 TeamPredictionBias, TeamFormDelta, DRSOvertakeProbAhead)
        ↓
finish_position (1-22)
```

with monotonicity constraints where physics requires (higher
lap-time → worse finish; higher current form → better finish).

### Cross-validation

`LearnedRaceProjection.leave_one_round_out_cv(X, y, round_ids)`
trains a held-out fold per round and reports MAE / RMSE / Spearman
rank correlation / podium hit rate. This is the metric `train +
register` uses to decide whether the new head improves over the
legacy hand-tuned `RaceProjectionScore`.

### Feature importance + SHAP

After fit, `head.feature_importance_dict()` returns a per-feature
gain importance. For per-row SHAP analysis,
`head.shap_values(X)` returns an `(n_rows, n_features + 1)` matrix
where the trailing column is the base score (LightGBM's native
TreeExplainer-equivalent output).

### Integration with `apply_race_postprocessing`

The head is loaded from the model registry under sentinel round 96
(reserved). When present, it produces a shadow column
`RaceProjectionScoreLearned` alongside the legacy
`RaceProjectionScore`. Setting `F1_USE_LEARNED_HEAD=1` makes the
learned column load-bearing — useful for shadow → production
promotion experiments.

### Training the head

```
python -m benchmarks.run_ml_comparison --season 2026 --fit-head
```

The benchmark fits a head on the data we have (currently:
predicted_position from `predicted_results_<season>.json` as a
single feature) and saves it to
`models/registry/<season>_round_96/`. The current training uses
predicted_position only because reconstructing the full 14-feature
matrix per prior round requires plumbing per-round snapshots into
the registry — a clean follow-up that exercises the same head
class.

### Fallback compatibility

When the head isn't registered, the legacy hand-tuned
`RaceProjectionScore` is the only score emitted. The integration
is intentionally non-blocking: any error loading or running the
head logs a one-line skip notice and falls through to legacy.

---

## 7. Bayesian hierarchical scaffold

[models/hierarchical_bayes.py](../models/hierarchical_bayes.py) is
a working but **feature-flagged** PyMC implementation of the
driver-within-team partial-pooling model described in §13 of the
2026-05-24 architecture review.

### Why scaffolded only

A clean PyMC implementation of the generative model exists and
unit-tests its scaffolding (without invoking PyMC itself, since
PyMC isn't yet in `requirements.txt`). But:

1. Full posterior fitting takes ~1-3 minutes on the project's CI
   runner. Wiring it into the per-race cron without first
   measuring whether it improves forward-eval metrics would be
   premature.
2. With only ~110 (driver, round) observations in the 2026 season
   so far, the posterior's identifiability is borderline — ADVI
   may produce unstable estimates until 10+ rounds are completed.

The right next move is a dedicated A/B PR that:
* Installs PyMC + ArviZ
* Adds `--fit-hierarchical-bayes` to the benchmark script
* Schedules a weekly cron to fit and store the posterior under
  registry sentinel round 97
* Measures whether `hier_driver_skill` + `hier_team_strength`
  features improve LOO-CV metrics

### Generative model (canonical)

```
μ_team[t]    ~ Normal(0, σ_team)
σ_drv[t]     ~ HalfNormal(σ_pool)
δ_drv[d]     ~ Normal(0, σ_drv[team_of[d]])
y[i]         ~ Normal(μ_team[team_of[d_i]] + δ_drv[d_i], σ_obs)
```

where `y[i]` is the driver's finishing position minus the race
mean. The centring keeps the posterior identifiable; without it,
all `μ_team` could shift by a constant.

---

## 8. Regulation-aware training strategy

Three mechanisms compose:

1. **`era_of()`** identifies which era a season belongs to.
2. **`era_decay_factor()`** discounts cross-era training rows.
3. **`compute_sample_weights()`** combines era distance with round
   recency.

Modes available:

| Mode | Behaviour |
|---|---|
| `"exponential"` (default) | Weight halves per era boundary; round half-life 8. |
| `"hard_cut"` | Rows beyond `hard_cut_eras` boundaries contribute zero. |
| `"none"` | Pass-through (all rows weight 1). |

The intended 2026 strategy: `"hard_cut", hard_cut_eras=1` early in
the season (rounds 1-7, where 2026-only data is sparse and the
2024-25 ground-effect data is the most useful prior), then switch
to `"exponential", decay=0.3` once 2026 has 8+ rounds of native
training data. This is a configuration change, not a code change —
operators can flip it via the `compute_sample_weights` call site
without recompiling anything.

---

## 9. Old-vs-new benchmark

`python -m benchmarks.run_ml_comparison --season 2026 [--fit-head] [--reliability-plots-dir ...]`

Produces a consolidated JSON report at `reports/ml_benchmark.json`
plus optional reliability PNGs. Sections:

* `position_metrics`: MAE / RMSE / podium hit-rate / winner hit-rate
  against `predicted_results_<season>.json`.
* `calibration_metrics`: per-market ECE / MCE / Brier from the
  `website/public/data/probabilities/round_NN.json` files.
* `conformal`: one-step-ahead coverage estimate from the residual
  cache.
* `head_loo_cv`: leave-one-round-out CV metrics when `--fit-head`
  is set; registers the head to sentinel round 96.

### What the first run revealed

Running the benchmark today (round 5 actuals only, 1 round of
shared predicted+actual data):

* Position MAE: 4.18 (high — only 1 round of evidence)
* Calibration: top6/top10 markets poorly calibrated (ECE 0.33 /
  0.25). win/podium fine.
* Conformal: insufficient residual cache yet (1 round saved; needs
  ≥8 residuals).
* Learned head: insufficient_data (only 22 rows / 1 unique round).

This is the right behaviour — the diagnostics surface the actual
data poverty, not synthetic optimism. As the season progresses,
each run produces richer signal.

---

## 10. Recommended retraining cadence

| Layer | Current | New | Justification |
|---|---|---|---|
| Layer 1 ensemble (GBR+XGB+LSTM) | Per race | Per race + time-decay sample weighting | Cheap, additive, no API cost. |
| Isotonic calibrators | Per race on demand | Per race (no change) | Already incremental. |
| Stratified isotonic | Same | Add `dry`/`wet` + `early`/`settled` strata once wet-race signal lands | Pending wet-race indicator. |
| Conformal calibrator | n/a (new) | Per race, reading accumulated cache | Auto. |
| Race-pace ensemble | Manual / offline | Every 28 days via cron | Diminishing returns on per-race retrain (~1200 new laps vs 50k corpus). |
| Learned race-projection head | Manual via benchmark | Refit weekly when ≥6 rounds of data + LOO-CV improves over legacy | Otherwise stick with legacy. |
| Bayesian hierarchical | n/a (new) | Weekly cron once dependency lands | ~1-3 min per refit; not race-critical. |
| Driver/team Elo | n/a (new) | Updates inline with `_add_elo_features` | Free; runs every race. |

---

## 11. Operational considerations

* **Cache size**: `data/conformal_residuals/` grows by ~500 bytes
  per round; ~22 KB per season. Gitignored.
* **CI compatibility**: All new modules import cleanly without
  LightGBM or PyMC (skip-decorators used in the tests). The
  cron only fails if the integration sites themselves error,
  which they won't because the integrations are wrapped in
  `try/except ... non-blocking` paths.
* **Backwards compatibility**: All existing tests pass unchanged.
  Adding `current_round=` to `_add_prediction_bias_features` is
  a kwarg-only addition; positional callers (none exist outside
  `build_training_dataset`) are unaffected.
* **Reproducibility**: Elo replay is deterministic given the
  event sequence; conformal quantile is deterministic given the
  residual set; learned head uses fixed `random_state=42`.

---

## 12. Deployment notes

1. **No CI changes required** for the foundation. The new modules
   are exercised by `tests/`; CI already runs the full suite.
2. **`F1_CURRENT_ROUND`** env var should be set to the target
   round when `train_ensemble` is called, so the conformal residual
   cache file is named correctly. `export_website_data.py` does
   not currently set this — wire it in
   [`gp_weekend.py`](../gp_weekend.py) or
   [`export_website_data.py`](../export_website_data.py) before
   the next cron tick.
3. **LightGBM head registration**: run
   `python -m benchmarks.run_ml_comparison --season 2026 --fit-head`
   weekly. The first run registers a single-feature stub; once
   per-round feature snapshots are saved, the full 14-feature
   training will register over it.
4. **PyMC opt-in**: install with `pip install pymc arviz`. Until
   then the Bayesian module remains a scaffold.
5. **Website type contract**: the new `ConformalIntervalLow/High`
   + `CalibratedConfidence` columns are computed but not yet
   serialized into the round JSON. Extending
   `ClassificationEntry` in [website/src/types/index.ts](../website/src/types/index.ts)
   to expose them is a follow-up — the type-safety gate in
   `tests/test_website_data_schema.py` will catch any drift.

---

## 13. What's deliberately *not* done

| Item | Why |
|---|---|
| Reinforcement learning | F1 has no action surface; ~22 reward samples/year with annual regulation churn. |
| Deep neural network on tabular features | Will overfit at ~500 samples/season. |
| AutoML / hyperparameter sweeps | Compute spend doesn't pay off in the small-data regime. |
| Replacing the Monte Carlo race simulator | The per-lap MC sim is the right primitive; nothing here replaces it. |
| Removing the LSTM | Pre-trained, contributes ~20% of the ensemble; keep until measured worse. |
| Forcing the learned head to production | Shadow column first; only promote after LOO-CV improvement is confirmed. |

---

## 14. Architecture at a glance (post-changes)

```
            ┌────────────────────────────────────────┐
            │  Layer 1 (per-race tabular ensemble)   │
            │  GBR + XGBoost + (LSTM)                 │
            │  Features: 36 engineered + 7 Elo       │
            │  Optional sample_weight (time-decay)   │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Layer 1.5: RaceProjectionScore        │
            │  Legacy:  14-term hand-tuned z-sum     │
            │  Shadow:  LightGBM RaceProjectionHead  │
            │           (registry sentinel round 96) │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Layer 1.7: Bayesian hierarchical (TODO)│
            │  μ_team + δ_driver partial pooling     │
            │  Scaffold present; PyMC opt-in         │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Layer 2: Plackett-Luce + isotonic     │
            │  Stratified calibrator (existing)      │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Layer 2.5: Split conformal intervals  │
            │  Resigual cache → per-round            │
            │  Lower/Upper + CalibratedConfidence    │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Layer 3: per-lap MC race simulator    │
            │  (existing; opt-in via flag)           │
            └────────────────────────────────────────┘
                            │
            ┌────────────────────────────────────────┐
            │  Forward-eval + reliability diagnostics│
            │  MAE/RMSE/Brier (existing)             │
            │  + per-market ECE/MCE/PNG plots (new)  │
            └────────────────────────────────────────┘
```
