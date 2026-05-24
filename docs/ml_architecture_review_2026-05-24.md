# F1 Predictions — ML Architecture Review

**Date:** 2026-05-24
**Scope:** Full technical evaluation of the prediction stack at the time of the Canada GP, with concrete recommendations for the rest of the 2026 season.
**Audience:** Engineering / modeling owners. This document is internal — it names implementation details that the user-facing pages must avoid per the tech-stack-scrub rule in [CLAUDE.md](../CLAUDE.md).

---

## 1. How the current model works

The pipeline is a **three-layer stack**. Layers 1 and 2 are wired into every race-weekend cron; Layer 3 is opt-in.

### Layer 1 — per-race regression ensemble

**File:** [f1_prediction_utils.py:1220-1408](../f1_prediction_utils.py)
**Target variable:** `AdjustedQualiTime` — the *qualifying* lap time, not the race finishing position.

Three regressors are fit per race, all on the same 22-driver × 35-feature design matrix:

- `GradientBoostingRegressor(n_estimators=200, …)`  *(scikit-learn)*
- `XGBRegressor(n_estimators=250, …)`  *(XGBoost)*
- Optional pre-trained LSTM on lap-time sequences

The ensemble blend uses **inverse-MAE weighting**: each member's weight is proportional to `1 / test_MAE`, so the best-performing model on the held-out drivers gets the largest share. The raw predicted spread is then **calibrated to realistic F1 gaps**: the script linearly rescales so the slowest-to-fastest gap is at most 3.5s (lines 1344-1354).

**Bootstrap intervals** (A-P2.3) ride alongside the point prediction: `PredictedLapTimeLow` / `PredictedLapTimeHigh` are 90% intervals from a bootstrap resample of the ensemble residuals.

**Train/test split:** `train_test_split` runs on *drivers within a single race*, not on rounds. That is, the "held-out" set is 4–5 drivers in the **same** race, sharing circuit, weather, tyres, and session state. This is **not a forward-time validation** — it's an in-distribution check on which drivers the ensemble can interpolate. Forward-time evaluation is done separately in [forward_eval.py](../forward_eval.py).

### Layer 1.5 — RaceProjectionScore post-processing

**File:** [f1_prediction_utils.py:1038-1177](../f1_prediction_utils.py)

The predicted lap time is converted into a **race ranking** via a hand-tuned weighted sum of 14+ z-scored features:

```
RaceProjectionScore =
    quali_lock_in   * z(quali_position) +
    pace_weight     * z(predicted_pace) +
    form_weight     * z(current_form) +
    consistency_w   * z(consistency_score) +
    bias_weight     * z(driver_prediction_bias) +
    team_bias_w     * z(team_prediction_bias) +
    overtake_term   * f(circuit_overtaking, grid_pos) +
    strategy_term   * f(undercut_edge, overcut_edge) +
    weather_term    * f(rain_probability) +
    sc_term         * f(circuit_safety_car) +
    teamorder_term  * f(team_order_pressure) +
    drs_term        * f(drs_overtake_prob) +
    teammate_term   * f(teammate_conflict_risk) +
    volatility_term * f(field_position_volatility)
```

The weights themselves shift dynamically by circuit characteristics (overtaking difficulty → higher `quali_lock_in`; rain probability → lower `quali_lock_in`, higher `volatility_term`).

Score is converted back to lap-time units (`RaceProjectionTime = min_time + 1.15 + z_score * 0.85`) so downstream code only ever consumes a lap-time field.

### Layer 2 — Plackett-Luce probabilities + isotonic calibration

**File:** [models/calibration.py:129+](../models/calibration.py)

The lap-time vector goes into a **Plackett-Luce sampler** via the Gumbel-max trick:

1. Convert lap times to exponential strengths: `λᵢ = exp(-(tᵢ - t_min) / τ)`, τ=0.5s.
2. Draw 5,000 full orderings: add Gumbel noise to `log(λᵢ)`, argsort descending.
3. Empirical market probabilities: `p_win`, `p_podium`, `p_top6`, `p_top10`, plus the pairwise head-to-head matrix.

Raw Plackett-Luce probabilities are then **isotonic-regressed** against historical `(predicted_p, observed_outcome)` pairs from `data/history.duckdb`. A `StratifiedProbabilityCalibrator` (A-P2.2) extends this with per-(market, stratum) fits and a global fallback.

**The honesty gate:** until ≥3 distinct (season, round) tuples exist in the history DB, `calibration.applied=false` is written and the raw Plackett-Luce numbers are published with a disclaimer banner. This is the right default — isotonic on 1–2 rounds collapses to a step function.

### Layer 3 — per-lap Monte Carlo race simulator (opt-in)

**Files:** [models/race_pace.py](../models/race_pace.py), [models/race_simulator.py](../models/race_simulator.py), [models/race_simulator_runner.py](../models/race_simulator_runner.py)

Trained offline from multi-season FastF1 lap-by-lap telemetry. A GBR+XGB ensemble predicts per-driver lap times from 16 lap-level features (driver/team/circuit IDs, lap number, lap progress, track position, tyre compound code, tyre age, gaps to cars ahead/behind, SC/VSC/yellow flags, air/track temp, rain intensity).

The simulator loops over a race: predict each driver's next lap, add noise, sample pit-stops, sample SC events from a Poisson process, update running gaps and positions. Default 2,000 MC samples. Output: `simulatorWinProbability`, `simulatorPodiumProbability`, `simulatorTop6Probability`, `simulatorTop10Probability`, `simulatorMeanFinish` per driver.

Registry sentinel: `models/registry/<season>_round_99/` with `metadata.kind=="race-pace"`. Opt-in via `--use-race-simulator`; silently no-ops if no race-pace ensemble has been registered.

---

## 2. Training data

| Source | What it provides | Refresh cadence |
|---|---|---|
| **FastF1** | Lap-by-lap telemetry, qualifying times, race results from 2018 onwards. Cached in `f1_cache/`. | On-demand; rate-limited to ~500 req/h. |
| **Ergast / Jolpica** | Full F1 result history 1950–present (positions + points; no lap-level data). | Nightly via [ergast_backfill.py](../ergast_backfill.py). |
| **OpenWeather** | Forecast temperature, rain probability per race weekend. | On-demand per round export. |
| **Season-results JSONs** | Current-season results curated for the 2026 calendar (rookie additions, mid-season swaps). | Manually maintained. |
| **`data/history.duckdb`** | `(season, round, driver, predicted_position, actual_position, predicted_lap_time)` — the calibration training reservoir. PK = `(season, round, driver)`. | Nightly via [backfill_history.py](../backfill_history.py); force-committed when changed (file itself is gitignored). |

### Feature catalogue (Layer 1)

35 columns in `DEFAULT_FEATURE_COLS` ([f1_prediction_utils.py:338-375](../f1_prediction_utils.py)). The natural groupings:

- **Pace** — `TeamAdjustedPace`, `CleanAirPace`, `BestLapTime`, `LapTimeStd`, `ConsistencyScore`, `TeamPerformanceScore`.
- **Circuit physics** — `CircuitOvertaking`, `CircuitSafetyCar`, `CircuitGripPenalty`, `ExpectedStopsFeature`, `SprintWeekend`.
- **Form / season state** — `CurrentForm`, `PreviousPosition`, `SeasonMomentum`, `PositionTrend`, `DriverPredictionBias`, `TeamPredictionBias`, `DriverDegComposite`, `TeamFormDelta`.
- **Strategy / game-theory** — `UndercutEdgeAhead`, `OvercutEdgeBehind`, `TeamOrderPressure`, `TeammateConflictRisk`, `DRSOvertakeProbAhead`.
- **Weather** — `RainProbability`, `Temperature`.
- **Grid context** — `QualifyingRank`, `GridAdvantage`, `PitTimeLoss`, `TyreDegFactor`, `ExperienceFactor`, `FieldPositionVolatility`, `LocalBattleIntensity`.

### Leakage discipline

[leakage.py:42-82](../leakage.py) exports `assert_prior_only(rounds_map, current_round, label)` and `assert_seasons_prior_only(...)`. Both raise `LeakageError` if any history key is ≥ `current_round`. The assertions are wired at:

- [f1_prediction_utils.py::build_training_dataset](../f1_prediction_utils.py)
- `_load_season_position_maps()` (filters strictly to prior rounds)
- [backfill_history.py](../backfill_history.py) and [ergast_backfill.py](../ergast_backfill.py) for the multi-season variant

The discipline is enforced at the boundary, not by trusting individual aggregators to filter themselves. This is the right design.

---

## 3. How predictions are generated

```
qualifying times (FastF1 or estimates)
        │
        ▼
35-feature training matrix per race
        │
        ▼
GBR + XGB (+ LSTM) ─── inverse-MAE blend ───► PredictedLapTime
        │
        ▼
RaceProjectionScore (14-term weighted z-score sum)
        │
        ▼
Race ranking + RaceProjectionTime
        │
        ▼
Plackett-Luce sampling (5000 draws, τ=0.5s)
        │
        ▼
Raw market probabilities (p_win, p_podium, …)
        │
        ▼
Isotonic calibration (gated on ≥3 historical rounds)
        │
        ▼
website/public/data/probabilities/round_NN.json
```

Where the seven prediction targets come from:

| Target | Mechanism |
|---|---|
| **Race winner** | `argmax(p_win)` from Plackett-Luce → isotonic. |
| **Podium positions** | Top-3 expected ranks from `RaceProjectionScore`; podium probabilities are `p_podium[driver]`. |
| **Qualifying results** | Direct from Layer 1 — the `AdjustedQualiTime` ordering, with bootstrap intervals. |
| **Driver standings** | Cumulative points: current standings + `Σ expected_points[round]` over remaining rounds (no separate model — derived from race probabilities × F1 points table). |
| **Constructor standings** | Same as driver, summed over team pairs. |
| **Finishing probabilities** | Plackett-Luce histogram per (driver, position). |
| **Upset probabilities** | Implicit in the Plackett-Luce tail — `p_top10[non_top10_grid_driver]`, `1 - p_top3[grid_p1]`, etc. No dedicated "upset model". |

---

## 4. Is the model continuously learning during the season?

**Yes, but in three different rhythms.**

| Layer | Retrains | Cadence |
|---|---|---|
| **Layer 1** (per-race ensemble) | Every round, from scratch, on prior-rounds-only data. | Each race weekend via [update_predictions.yml](../.github/workflows/update_predictions.yml). |
| **Layer 2** (isotonic calibrators) | Refit on demand from the growing `data/history.duckdb`. | Each `export_probabilities.py` invocation. |
| **Layer 3** (race-pace ensemble) | Manually via `train_race_pace.py --seasons 2018-2025`. | **Not in the weekend cron** — multi-season FastF1 fetch would blow the 500 req/h rate limit. |

Supporting infrastructure that grows the learning surface every night:

- **Nightly backfill** ([.github/workflows/backfill_history.yml](../.github/workflows/backfill_history.yml), 03:00 UTC): runs Ergast (Tier 2) + a rate-limited slice of FastF1 (Tier 1), then force-commits `data/history.duckdb` if changed.
- **Online game-theory coefficients** ([models/online_game_theory.py](../models/online_game_theory.py)): ridge regression on the 7 `RaceProjectionScore` coefficients, exponentially blended with the legacy values (α=0.30, ~2-round half-life). Registry sentinel round 98.
- **Promotion gate** ([models/promotion.py](../models/promotion.py)): production vs candidate stream, requires ≥5 overlapping rounds + 2% mean improvement + no per-round 20%+ regression before recommending promote.
- **Drift report** ([drift_report.py](../drift_report.py)): PSI per feature against baseline + rolling Brier trend. Severity bands at PSI 0.10/0.25 and Brier 5%/15% regression.

So the system **already does meaningful continuous learning** for Layers 1 and 2, and has the infrastructure for a guarded version of Layer 3 retraining.

---

## 5. Would retraining after each completed GP improve accuracy further?

**Layer 1 — already done. Marginal headroom from changes here.** The ensemble is refit from scratch every weekend. The bigger question is *what data window it trains on*; see §6.

**Layer 2 — already done; can be tightened.** The isotonic calibrator already absorbs each new round's results via the nightly backfill. The honest improvement here is **per-stratum calibration coverage** — `StratifiedProbabilityCalibrator` exists but its strata coverage is sparse early in a new regulation year like 2026. Worth measuring per-stratum sample counts and downgrading to the global fallback when a stratum has <10 observations.

**Layer 3 — refit monthly, not weekly.** The race-pace ensemble trains on a 50,000+ lap-level corpus from FastF1. A single new race adds ~1,200 driver-laps. Per-race incremental retraining buys little signal and burns the FastF1 rate budget. A monthly cadence (≈ every 4 races) gives meaningful new lap coverage without hammering the API. Wire it into the cron with a `--if-last-trained-older-than 28d` gate, keep the offline manual path as the override.

**Game-theory coefficients — already done.** [models/online_game_theory.py](../models/online_game_theory.py) blends the new ridge fit with the legacy values at α=0.30 every race. That's a ~2-round half-life. This is the right shape for a continuously-updated weight head.

### Net recommendation on retraining frequency

| Surface | Current | Recommended |
|---|---|---|
| Layer 1 ensemble | Per race | Per race ✓ keep |
| Isotonic calibrators | Per race (on demand) | Per race ✓ keep |
| Stratified calibrator strata | Same | Add coverage gate + auto-fallback |
| Race-pace ensemble | Manual / offline | Cron at ~28d intervals; guarded by promotion gate |
| Game-theory weights | Per race, α=0.30 blend | Per race ✓ keep |

---

## 6. Static vs rolling retrained — which would perform better?

**Rolling, with a regulation-change-aware window.** The static-vs-rolling question is the wrong framing for F1 — the right framing is *what training window matches the current regulation regime*.

Three observations drive this:

1. **F1 regulations change yearly** (sometimes mid-season). 2026 is a major regulation change (new power-unit formula, active aero, lighter cars). Pre-2026 race-pace data describes physically different cars. Treating 2023–2025 lap times as fully comparable to 2026 is a known leak of distributional drift into the training set.

2. **Driver-team pairings change yearly.** A 2024 lap time for HAM-Mercedes is a different sample from a 2026 lap time for HAM-Ferrari. The race-pace model conditions on `(driver_id, team_id)` separately, but the *interaction* is what matters and is implicit.

3. **The sample is genuinely small.** 22 rounds × 22 drivers × ~50 laps = ~24,000 race-laps per season; ~500 quali samples per season. Discarding old data costs you variance; keeping old data costs you bias. Time-decay weighting is the right tradeoff.

### Concrete recommendation

For **Layer 1**: keep the current per-race retraining, but add **exponential time-decay weighting** to the training rows. Recent races weighted more heavily, prior-season races still contribute (with a half-life of ~8 rounds = roughly a third of a season). This is one extra column in the design matrix and one `sample_weight` argument to `fit`. Cheap and easy to backtest.

For **Layer 3**: explicit **2024-and-newer hard cut** for 2026 race-pace training, *or* exponential decay with a half-life of ~1 season. After Round 8 of 2026, you'll have enough native 2026 data to switch to 2026-only training and treat 2024–2025 as cold-start priors only.

For **Layer 2**: stratified isotonic already gives partial sliding-window behaviour. Add a "season recency" stratum to the existing strata.

---

## 7. How is prediction confidence calculated?

**File:** [f1_prediction_utils.py:1158-1177](../f1_prediction_utils.py)

The raw uncertainty score sums four heuristic terms:

```python
raw_uncertainty = (
    model_dispersion           # std-dev across (GBR, XGB, LSTM) predictions
    + consistency_penalty       # ConsistencyScore * 18.0
    + position_trend_variance   # rolling variance of recent positions
    + |DriverPredictionBias| * 0.06
    + |TeamPredictionBias| * 0.08
    + field_volatility          # 0.55*overtake + 0.25*rain + 0.20*safety_car
    + battle_intensity          # LocalBattleIntensity
    + teammate_conflict         # TeammateConflictRisk
    + base_volatility           # 0.20
)
```

Then it's percentile-clipped to `[20th, 85th]`, mapped linearly to `[0, 1]`, and bucketed into `{low, medium, high, very_high}` for the UI.

**This is an unreliable confidence signal.** Three problems:

1. **It's not measured for reliability.** A confidence number should mean something — "high confidence" should correspond to ~90% empirical accuracy across many high-confidence predictions. Nothing in `forward_eval.py` currently produces a reliability diagram or an ECE (Expected Calibration Error) number for the confidence bands.

2. **The percentile clip destroys signal.** A linear remap on percentile rank discards the actual magnitude of raw_uncertainty — two races whose true uncertainty differs by 3× look similar after the clip if the rest of the field is similarly spread.

3. **It's a sum, not a model.** The eight terms have no relative empirical weighting — coefficients like `0.06` and `18.0` are hand-set.

### Recommendation

Replace the hand-tuned confidence score with **split conformal prediction intervals** on the lap-time output:

- For each predicted `PredictedLapTime`, the conformal interval is `[ŷ - q_α(residuals), ŷ + q_α(residuals)]` where `q_α` is the α-quantile of held-out residuals from prior rounds.
- Coverage guarantee: ~(1−α) of true lap times fall inside the interval, under exchangeability. F1 has obvious exchangeability violations (regime change after rounds 1–2 of a new season, weather races) — handle by **stratifying** the calibration set: separate quantiles for dry vs wet, for newly-introduced circuits vs known, for early-season vs settled.

Costs: ~1 day of work, 0 new dependencies (numpy quantile is enough). [`mapie`](https://github.com/scikit-learn-contrib/MAPIE) would give the off-the-shelf API but is currently blocked in `requirements-dev.txt` by the sklearn version conflict — the hand-rolled split-conformal version is fine.

Add **reliability diagrams + ECE** to `forward_eval.py` for the existing market probabilities at the same time. Both are ~30 lines of code each and would give the first honest measurement of how trustworthy the confidence banner on each round actually is.

---

## 8. Is reinforcement / self-learning appropriate for F1?

**No — not as a primary mechanism.** Reinforcement learning needs an environment the agent acts inside, with reward signals that come from those actions. F1 doesn't fit that mold from the prediction side:

- **There is no action surface.** The model predicts; the race happens; we score the prediction. Nothing the model does changes the race outcome. The closest fit is the *bet-sizing* layer — a Kelly-style staking strategy could be cast as a bandit problem, but the project's `/value` page was removed in the 2026-05-21 redesign and the betting flow is dormant.
- **Reward sparsity is brutal.** 22 races per year, with regulation changes every year, means a budget of ~22 reward samples per regime change. RL training in that regime overfits to the trajectory.
- **Exploration is impossible.** RL needs the agent to occasionally take suboptimal actions to learn the environment. You can't "explore" by deliberately publishing bad predictions; you can't "explore" in a real race.

What *is* appropriate and already partly in place is **online supervised learning** — which the system has under another name:

- **Online isotonic calibration** (Layer 2): updates per race, no exploration needed.
- **Online ridge regression** on game-theory coefficients ([models/online_game_theory.py](../models/online_game_theory.py)): exponential blend with prior values.
- **Shadow/candidate promotion** ([models/promotion.py](../models/promotion.py)): A/B test new models against production on rolling 5-round windows.

These are the right surfaces for "self-learning" in an F1 context. Stretch the existing pattern (ridge regression with exponential blend) to **any other hand-set coefficient** in the codebase — confidence weights, calibration temperature τ, pace-vs-form weight in `RaceProjectionScore` — and treat them as online-learned parameters with a low-α blend against priors.

If the betting flow is ever revived, then a **contextual bandit on bet sizing** (LinUCB, Thompson sampling on a Bayesian posterior of edge × payoff) is the right tool. Don't try to make the prediction model itself an RL agent.

---

## 9. Strengths of the current architecture

1. **Disciplined leakage prevention.** [leakage.py](../leakage.py) raises at the boundary, not by hoping aggregators self-filter. CI gates depend on it. The single best property of the codebase.

2. **Honesty-gated calibration.** The `calibration.applied=false` default until ≥3 rounds is exactly right. Refusing to publish a poorly-calibrated probability is more valuable than publishing one with confidence.

3. **Three-layer modularity.** Lap-time model, probability calibration, and race simulator can each be replaced or A/B-tested without touching the others. The contract between layers (a `classification[*].predictedTime` JSON field) is narrow and clean.

4. **Model registry with metadata-only commits.** [models/registry.py](../models/registry.py) versions every fit. `metadata.json` is committed (auditable); binaries are gitignored (repo size stays sane). Promotion decisions reference past artifacts by `(season, round)`.

5. **Forward-time evaluation is a separate, scheduled step.** [forward_eval.py](../forward_eval.py) doesn't share data with `train_ensemble` — it scores predictions against actuals after the race, computes MAE/Brier/Spearman/NDCG@5, and writes per-round JSON. CI guarantees it runs.

6. **Drift monitoring + promotion gate.** PSI/Brier trends + the 5-round overlap requirement + 2% mean-improvement gate stop quiet regression from creeping into production.

7. **Pre-commit pytest gate.** [.github/workflows/update_predictions.yml](../.github/workflows/update_predictions.yml) runs `tests/test_website_data_schema.py` + `test_predictions_sanity.py` *before* committing the regenerated round JSONs. Degenerate output (all-NaN, missing drivers, duplicate positions) never reaches GitHub Pages.

---

## 10. Weaknesses and risks

### Overfitting risks

1. **Hand-tuned `RaceProjectionScore` weights.** Fourteen coefficients chosen by intuition. Even with online learning on a subset (game-theory layer), the bulk of weights are static. Replace with a **learned head**: a small linear/tree regression from `(predicted_lap_time, all 14 features)` → `actual_finish_position`, trained on the same `data/history.duckdb` that powers calibration. Cross-validate by leave-one-round-out. The expected gain is moderate but the variance reduction is real.

2. **LSTM contribution is unprincipled.** The LSTM weight is part of the inverse-MAE blend but the LSTM was trained on a *different* corpus (lap-time sequences across many seasons) — it isn't being fit to the per-race data. Inverse-MAE on a small held-out set in the same race over-weights whichever model happens to fit the 4-5 test drivers, which is a noisy signal.

3. **Per-race driver-split is not a generalization signal.** Same circuit, same weather, same tyres → 5 held-out drivers tell you nothing the 17 trained drivers didn't. The per-race "test MAE" used to weight the ensemble is biased. Use **leave-one-round-out cross-validation** over prior rounds to set ensemble weights, refit weekly. Computationally cheap (~22 fits per round; each fit takes seconds).

### Data leakage risks

4. **`DriverPredictionBias` and `TeamPredictionBias` are residuals from prior predictions** ([f1_prediction_utils.py:540-585](../f1_prediction_utils.py)). The aggregation iterates over a `predicted_results` dict — the safety of this depends entirely on the caller filtering to prior rounds only. The function itself does not assert `assert_prior_only(predicted_results, current_round, "bias_history")`. Add the assertion at the entry point of `_add_prediction_bias_features`. Small change, removes a footgun.

5. **The `weight = exp(0.35 * rnd)` schedule in the same function** scales prior rounds exponentially. At round 6, round 5 gets `exp(1.75) ≈ 5.75×` the weight of round 1. That's a steep schedule — verify empirically that this isn't double-counting recent residuals already captured by `CurrentForm`.

6. **`RainProbability` and `Temperature` are forecasts at export time**, not actuals. For historical rounds, regenerating the export with `--weather` would inject *current* weather as if it were the forecast. The default (no `--weather`) uses static heuristics — safer but inaccurate. Lock the forecast at export time and store it in the round JSON; don't recompute on regeneration.

### Generalization risks

7. **Layer 3 race-pace ensemble is trained on 2018–2025 data** with no regime-change weighting. 2026 cars are physically different. Untreated, the race simulator will be biased toward the dynamics of older formulas through the early 2026 season.

8. **Cold-start for rookies is undefined.** A new driver (e.g., Hadjar, Lindblad) has no prior-round data. `DriverPredictionBias` defaults to 0; `CurrentForm` defaults to mid-pack. There's no explicit "rookie regularization to team mean" — the model implicitly treats them as average. Add a `rookie=True` indicator + partial-pool toward team-mean for the first 5 rounds.

### Calibration risks

9. **Sample sparsity for tail markets.** 22 rounds × 22 drivers = 484 (driver, round) pairs per season for isotonic. That's enough for `p_win` and `p_podium`. It's marginal for `p_top10` (large outcome class). It's poor for "exactly P3" or "DNF" markets.

10. **The percentile-clipped confidence bucket is not calibration.** See §7.

---

## 11. Best practices in sports prediction systems — gap analysis

| Practice | Status |
|---|---|
| Forward-time evaluation that's separate from training | ✓ Done ([forward_eval.py](../forward_eval.py)) |
| Honesty gate on calibrated outputs | ✓ Done (`calibration.applied=false` default) |
| Drift monitoring (feature PSI + outcome Brier) | ✓ Done ([drift_report.py](../drift_report.py)) |
| Shadow / candidate A-B promotion | ✓ Done ([models/promotion.py](../models/promotion.py)) |
| Pre-commit sanity test gate on output JSON | ✓ Done |
| Time-decay sample weighting in training | ✗ Not done |
| Per-stratum reliability diagrams | ✗ Not done |
| ECE in forward-eval | ✗ Not done |
| Conformal prediction intervals | ✗ Not done |
| Explicit cold-start handling for rookies | ✗ Not done |
| Brier skill score vs `last_race_winner` baseline | ~ Partial (baseline exists; SS not explicitly published) |
| Elo / glicko driver-team rating as a feature | ✗ Not done |
| Bayesian hierarchical pooling (driver-within-team) | ✗ Not done |

---

## 12. Algorithm selection — what to keep, what to add, what to skip

### What to keep

- **XGBoost + GradientBoosting (sklearn)** as the primary regressors. Tree boosting is the right tool for ~500-sample tabular problems with strong feature interactions. Both ship now; the inverse-MAE blend is fine.
- **LightGBM** belongs alongside as a third member of the ensemble. Faster than XGBoost on small data, often slightly better on tabular regression. Cheap addition, ~50 lines.
- **Monte Carlo race simulator** as Layer 3. The per-lap framing is the physically correct way to express pit-stop decisions, SC events, traffic. Keep it.
- **Plackett-Luce + isotonic** as Layer 2. Standard sports-prediction stack. Well-suited to small-N calibration.

### What to add (in priority order)

1. **Driver and team Elo features** — as features, not as a separate model. Elo updates take 5 minutes to wire. Drivers update on (predicted finish vs actual finish); teams update on aggregated driver Elos. The big win is **cold-start handling** for rookies and mid-season swaps — Elo gracefully assigns priors and updates from there. Feed the Elo number into `DEFAULT_FEATURE_COLS`. **Cost: ~1 day. Expected lift: small but consistent across markets.**

2. **Bayesian hierarchical model for partial pooling (PyMC)** — fit weekly on `(driver, team, circuit, finish_position)`. Posterior gives `μ_driver_at_team` for every observed pair. Use as a prior in `RaceProjectionScore` or as a feature. The right tool for "Hadjar at Racing Bulls vs Hadjar at Red Bull" reasoning, and PyMC handles small-N gracefully because of the regularization. **Cost: ~3-5 days. Expected lift: moderate, especially for non-leader markets.**

3. **Conformal prediction intervals** on the lap-time output — replaces the percentile-clip confidence buckets. **Cost: ~1 day.**

4. **Time-decay sample weighting** in Layer 1's `fit()` call. **Cost: 1 hour.**

5. **Reliability diagrams + ECE** in forward-eval. **Cost: ~1 day.**

6. **Learned head replacing the hand-tuned `RaceProjectionScore`**. Linear or LightGBM regression from `(predicted_lap_time + 14 features)` → `finish_position`, fit on `history.duckdb`. **Cost: ~2 days. Expected lift: moderate.**

### What to use sparingly

- **Neural networks.** The current LSTM is fine as a pre-trained component contributing to the ensemble blend, but **don't expand neural-net surface area**. With ~500 quali samples per season, transformers / GNNs / sequence models will overfit and add little signal. The current ensemble blend underweights the LSTM correctly via inverse-MAE — leave it that way.

### What to skip

- **Reinforcement learning** as a prediction mechanism (see §8).
- **AutoML** (TPOT, AutoSklearn) — encourages overfitting in small-N regimes; you'd burn compute on irreproducible improvements.
- **Deep ensemble of 50 XGB seeds** — diminishing returns past 3-4 models in this sample regime.

### Recommended target ensemble

```
                  ┌─────────────────────────────────────────────┐
                  │  Layer 1: per-race tabular ensemble         │
                  │  ─ XGBoost (race ranking)                   │
                  │  ─ LightGBM (lap time)                      │
                  │  ─ GBR (sklearn, baseline)                  │
                  │  ─ LSTM (pre-trained, low-weight)           │
                  │  ─ Inverse-MAE blend on LOO-CV scores       │
                  │  Features: existing 35 + Elo (new)          │
                  │  Training: time-decay weighted              │
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Layer 1.5: learned RaceProjection head      │
                  │  ─ Replaces hand-tuned weighted sum         │
                  │  ─ LightGBM on (lap_time + 14 features)     │
                  │    → finish_position                        │
                  │  ─ LOO-CV over prior rounds                 │
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Layer 1.7: Bayesian hierarchical prior     │
                  │  ─ PyMC, fit weekly                         │
                  │  ─ Partial pooling: driver-within-team      │
                  │  ─ Posterior → feature OR Plackett-Luce τ   │
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Layer 2: Plackett-Luce + isotonic          │
                  │  ─ Already in place                         │
                  │  ─ Add: stratified by dry/wet, early/settled│
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Layer 2.5: conformal intervals             │
                  │  ─ Replaces percentile-clip confidence      │
                  │  ─ Split conformal on lap-time residuals    │
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Layer 3: per-lap MC race simulator         │
                  │  ─ Already in place                         │
                  │  ─ Retrain monthly with 2024+ time-decay    │
                  └─────────────────────────────────────────────┘
                                  │
                  ┌─────────────────────────────────────────────┐
                  │  Continuous-learning surfaces               │
                  │  ─ Online isotonic refit (in place)         │
                  │  ─ Online game-theory ridge (in place)      │
                  │  ─ Online Elo updates (new)                 │
                  │  ─ Shadow/candidate promotion gate (in place)│
                  └─────────────────────────────────────────────┘
```

---

## 13. Recommendations summary

**Do now (within 1 week):**
1. Add `assert_prior_only` at the entry of `_add_prediction_bias_features`.
2. Add **driver + team Elo** as features, with per-race updates.
3. Add **time-decay sample weighting** to Layer 1's `fit()`.
4. Add **reliability diagrams + ECE** to `forward_eval.py`.

**Do this month (within 4 weeks):**
5. Replace the percentile-clip confidence with **split conformal intervals**.
6. Replace hand-tuned `RaceProjectionScore` with a **learned head** (LightGBM).
7. Schedule Layer 3 race-pace retrain on a **28-day cron** with 2024+ time-decay.
8. Add **rookie cold-start partial pooling** to team mean (first 5 rounds).

**Do this quarter (within 12 weeks):**
9. Stand up the **Bayesian hierarchical prior** (PyMC, weekly fit).
10. Stratified isotonic with **dry/wet + early-season/settled** strata.
11. Resolve the `mapie` / sklearn version conflict in `requirements-dev.txt` so the conformal layer can use a maintained library.

**Do not do:**
- Reinforcement learning on the prediction surface.
- Deep neural networks beyond the existing LSTM blend member.
- AutoML / hyperparameter sweeping the whole stack.

---

## 14. Honest limits

The single biggest constraint is sample size. 22 rounds × 22 drivers, with year-on-year regulation churn, gives a training set whose effective independent sample size is closer to a few hundred than to several thousand. Every architectural choice above respects that: tree boosting over deep nets, partial pooling over flat hierarchies, conformal intervals over learned uncertainty heads, isotonic over neural calibration.

The best lift will come from the small, principled additions (Elo, conformal, learned head replacing magic numbers, ECE measurement) — not from any single new model. The architecture is already sound; the wins are in tightening what's there.
