# motorsport-core API reference

Sport-agnostic ML and evaluation infrastructure. `pip install -e packages/motorsport-core`.

## `interfaces`

The plug-in seam. Dataclasses: `Competitor`, `Venue`, `GridEntry`,
`RoundForecast`. ABCs: `DataSource`, `Predictor`. Re-exports
`MarketProbabilities` from `calibration` as the canonical probability type.

## `calibration`

Plackett-Luce ranking sampler + isotonic / stratified calibration.

- `plackett_luce_probabilities(lap_times, n_samples=5000, temperature=0.5, seed=42) -> MarketProbabilities`
  — Monte Carlo race simulation → per-competitor win/podium/top6/top10 + H2H.
- `ProbabilityCalibrator` / `StratifiedProbabilityCalibrator` — isotonic fit from
  historical `(predicted_p, observed_outcome)` pairs, with honest gating until
  enough history exists.
- `calibrate_market_probabilities(...)`, `collect_history_from_rounds(...)`.

## `probability_coherence`

`coherent_top_k(probabilities, targets, floor=0) -> ndarray` projects a
competitor-by-market matrix onto nested top-k probabilities with fixed column
sums and bounds. Dykstra's algorithm combines row isotonic projections with
bounded-simplex column projections; non-convergence fails explicitly.

`calibration.renormalize_market_struct` applies this after per-market
normalization when markets share a field, then rounds once. Raw simulation
probabilities remain unchanged. The repair enforces logical constraints; it
is not a claim of better calibration or out-of-time accuracy. Unknown, empty,
and all-zero markets retain their existing handling.

## `registry`

`ModelRegistry().save(season, round_num, models, metadata)` → joblib/torch
artefacts + committed `metadata.json` under `<season>_round_<NN>/`. Atomic writes.

## `drift`

- `population_stability_index(baseline, current, n_bins=10) -> float`
- `classify_psi(psi) -> "ok" | "warn" | "alarm"`
- `rolling_brier_trend(...)`, `build_health_report(...)`.

## `promotion`

`evaluate_promotion(production_scores, candidate_scores, …) -> PromotionDecision`
— guarded A/B gate (min overlap, relative-improvement threshold, per-round
regression cap, and a positive paired-round bootstrap improvement interval).
The overlap floor applies to the trailing window; scores must be finite and
nonnegative. Perfect-score regressions block promotion.

## `eval`

CLI-free forward-time ranking metrics over `{competitor: position}` maps:
`spearman_correlation`, `ndcg_at_k`, `mean_position_error`, `within_n`,
`score_round`, `last_order_baseline`.

## `standings`

Championship standings from race results (sport-agnostic; points table is a
parameter so any series fits):

- `compute_driver_standings(results, points, *, bonus=None) -> list[StandingRow]`
- `compute_team_standings(results, points, team_of, *, bonus=None)`
- `merge_standings(*tables)` — combine standings computed under different points
  tables (multi-race weekends: F2 sprint+feature, F1/MotoGP sprint).

Ties break by countback (wins → podiums → best finish).

## `championship`

Monte Carlo title projection:

- `project_championship(current_points, strengths, remaining_rounds, points, *, n_samples=5000, races_per_round=1, seed=42) -> list[TitleProjection]`

Reuses `calibration.sample_finishing_orders` for per-round sampling (no
duplicated logic). Each `TitleProjection` carries `p_title` and a projected
final-points distribution (`proj_mean`, `proj_p10`, `proj_p90`).

## `calibration.sample_finishing_orders`

`sample_finishing_orders(values, n_samples, temperature, seed) -> list[list[str]]`
— the reusable Plackett-Luce primitive that returns full sampled finishing
orders (the engine shared by the single-race probability layer and the
championship Monte Carlo).

## `elo` (+ `era`)

Pairwise competitor/team Elo. `era.era_distance(a, b)` is lenient — returns 0 for
seasons outside the configured `ERAS` table, so sports without regulation-era
awareness incur no penalty. Replace `ERAS` to enable it.

## `conformal`, `reliability`, `hierarchical_bayes`

Conformal refits discard old state, including absent strata. The finite-sample
quantile is the `ceil((n+1)*(1-alpha))`th residual. If that rank exceeds the
sample size, fitting raises rather than advertising a finite coverage guarantee.
Calibration inputs must be finite one-dimensional arrays. Coverage still relies
on exchangeability; this change does not establish that assumption for racing.

Conformal prediction intervals; reliability diagrams + ECE/MCE
(plotting needs the optional `matplotlib`); Bayesian skill priors.

## `features`

- `features.skill_priors` — blended driver/team/venue Bayesian prior.
- `features.competitor_history` — per-(competitor, venue) history aggregation.

## `leakage`

`assert_prior_only(rounds_map, current_round, label)` and
`assert_seasons_prior_only(...)` — temporal-leakage guards to call at every
multi-round aggregation boundary.

## `temporal_skill` (research candidate)

`predict_temporal_skill(prior_rounds, feature_columns, features_before, actual_for,
half_life_rounds=6, min_training_rows=8) -> TemporalSkillPrediction | None`

Builds one set of training rows per historical target event, with features from
strictly earlier rounds. Holds out the last completed event to choose a blend
of gradient boosting and historical mean, then refits using recency weights.
Returns predictions, the chosen weight, validation errors and training cutoffs.
Feature callbacks must replay their historical information set; never pass
current-cutoff Elo into old training rows. This module does not promote a model.
See the [platform audit](PLATFORM_IMPROVEMENT_AUDIT.md) and the F2/F3 opt-in adapters.
