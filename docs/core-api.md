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
regression cap). Scores are lower-is-better.

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

Conformal prediction intervals; reliability diagrams + ECE/MCE
(plotting needs the optional `matplotlib`); Bayesian skill priors.

## `features`

- `features.skill_priors` — blended driver/team/venue Bayesian prior.
- `features.competitor_history` — per-(competitor, venue) history aggregation.

## `leakage`

`assert_prior_only(rounds_map, current_round, label)` and
`assert_seasons_prior_only(...)` — temporal-leakage guards to call at every
multi-round aggregation boundary.
