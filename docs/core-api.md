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
- **`renormalize_market_struct(struct, *, digits=None)` — call this on every
  market struct before publishing it.** Per-competitor isotonic calibration maps
  each probability independently, so a market stops summing to the size of the
  set it describes (`MARKET_TARGET_SUM`: win 1, podium 3, top6 6, top10 10). It
  water-fills back to the target: scale, cap at 1.0, redistribute. Round
  **after**, via `digits` — rounding first reintroduces the drift. Markets with
  no fixed set size (`dnf`) pass through untouched, and a field smaller than the
  market clamps to the field rather than inflating six cars to fill ten slots.
  `rawProbability` is never modified, so the pre-calibration number stays
  auditable beside the published one.

  Skipping this is not cosmetic: it published win markets summing to 2.00 across
  five series for a month. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

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

## `evidence`

Builds the one artifact every site's `EvidencePanel` renders, so the
model-vs-baseline comparison is computed once in Python instead of six times in
TypeScript.

- `build_evidence(forward_eval_dir, *, calibration_summary=None, promotion_status=None, sport=None) -> EvidenceBlock`
  — reads a project's published `forward_eval/` tree. Handles both published
  shapes: the feeder shape (`baselines` keyed by race type) and the single-race
  shape (`baselines` keyed by baseline name).
- `compare_paired(metric, paired, *, baseline, race_type) -> Comparison` — one
  metric, **paired on the rounds both sides scored**. Comparing two
  independently-averaged means over different round sets is the mistake this
  exists to make impossible.
- `paired_bootstrap(differences, *, resamples=2000, seed=…)` — percentile CI on
  the paired difference. Seeded: a published artifact that changes when nothing
  changed is a diff every morning.
- `write_evidence(block, out_path)`.

Verdicts are `better` / `worse` / `inconclusive` / `insufficient`. Below
`MIN_ROUNDS_FOR_CLAIM` (5) it is `insufficient` however good the delta looks —
the same overlap floor `promotion` applies, because the two gates disagreeing
would let a claim reach the site that could not reach production. A CI
straddling zero is `inconclusive`, never the sign of the point estimate.
`METRIC_DIRECTION` records which metrics are lower-is-better, and `improvement`
is always oriented so positive means the model is better.

## `integrity`

Checks over a project's **published** `website/public/data/` tree — the question
a per-file schema test cannot answer, because every file can be well-formed
while the corpus is wrong.

- `check_published_data(data_dir, *, project=None, root=None) -> Report`

Checks: `round_files_contiguous`, `chronological`, `no_future_results`,
`no_duplicate_competitors`, `no_placeholder_entrants`, `probability_range`,
`probability_mass`, `baselines_published`, `calibration_gate_honest`,
`season_manifest`, `drift_vocabulary`. Each returns a `Finding` naming the file
and the fact. Missing optional artifacts are **skipped, not failed** — a
scaffolded series has no forward-eval, and that is a maturity level.

Run over everything with `python scripts/validate_published_data.py`.

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
