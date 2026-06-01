# Model Card — RaceIQ (2026 season)

This card documents the predictive model that powers the RaceIQ
website. It follows the
[Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993) format and
is the canonical reference for what the model is, what it is **not**, and the
honest limits of what it can claim.

---

## Intended use

- **Primary**: educational F1 race-outcome predictions surfaced through the
  Next.js dashboard at `/`, `/race/[round]`, `/standings`, and `/accuracy`.
  These are point-in-time forecasts; the audience is F1 fans curious about
  data-driven race previews.
- **Secondary**: a value-finder at `/value` for **personal informed-decision
  use**. The page compares calibrated model probabilities with bookmaker odds
  to surface positive-edge bets and a fractional-Kelly suggested stake. **This
  is not financial advice**, not a tip service, and not a regulated product —
  the page carries an explicit disclaimer to that effect.
- **Out of scope**: automated bet placement; underage targeting; resale as a
  prediction service.

---

## Data sources

- **FastF1 (2023+)**: lap-by-lap telemetry, qualifying, race classification,
  tyre stints, pit stops. Cached locally under `f1_cache/`. Primary training
  signal for the lap-time regression.
- **OpenMeteo (free tier)**: pre-race weather forecasts (temperature, rain
  probability) for the circuit on race day. Cached under `weather_cache/`.
- **Jolpica/Ergast-compatible API**: official driver + constructor standings
  and completed-round classified results, used to keep the website data in
  sync with reality once a race weekend ends. Toggled with
  `F1_USE_LIVE_STANDINGS` and `F1_USE_LIVE_ROUND_RESULTS` — see
  [`docs/ENV_VARS.md`](docs/ENV_VARS.md).
- **2026 calendar**: pulled from formula1.com and persisted in
  `races/round_NN_*.py` plus the seasonal config. 22 rounds, 6 sprint
  weekends, 22 drivers across 11 teams (including the new Cadillac entry).
- **The Odds API**: bookmaker odds for the `/value` page —
  **but F1 is not currently in their catalog** (verified 2026-05). See the
  "Known limitations" section below and `docs/ENV_VARS.md` for the
  alternative-source plan.

---

## Training procedure

Per-race, in-race training (no global multi-season retrain — see Known
limitations):

1. **Feature build** (`f1_prediction_utils.py`): per-driver features assembled
   from historical telemetry, qualifying pace, circuit characteristics, tyre
   wear factor, current-form / season-momentum aggregates from prior rounds,
   team-change adjustments. Leakage discipline enforced via
   `leakage.assert_prior_only` / `assert_seasons_prior_only` — features
   aggregated over rounds must never include data from the target round or
   later, and the assertion fires loudly if a caller breaks the contract.
2. **Regression target**: `AdjustedQualiTime` (driver lap time normalised for
   conditions). The model regresses lap time rather than finishing position
   directly.
3. **Ensemble**: a `GradientBoostingRegressor` + `XGBRegressor`, both with
   `random_state=42` pinned, blended via a weight learned on a 20% held-out
   split per round. Feature scaling via `StandardScaler` (fit on training
   split only).
4. **Postprocessing**: `apply_race_postprocessing` (in
   `f1_prediction_utils.py`) applies game-theory adjustments — undercut /
   overcut / DRS / battle / teammate-conflict / field-volatility terms —
   gated by `ENABLE_GAME_THEORY_ENHANCEMENTS` and scaled by
   `F1_GAME_THEORY_POSTPROCESS_SCALE` (default `1.2`, calibrated by
   `optimize_game_theory_postprocessing.py` over completed 2026 rounds 1–3).
5. **Probability layer** (`models/calibration.py`,
   `export_probabilities.py`): predicted lap times are converted to
   Plackett–Luce strengths `λᵢ = exp(-(tᵢ - t_min) / τ)` with `τ = 0.5s`. A
   Monte Carlo over `N=5000` Plackett–Luce samples (`np.random.default_rng(seed=42)`)
   yields empirical `P(win)`, `P(podium)`, `P(top6)`, `P(top10)`, and a full
   head-to-head matrix `P(A finishes ahead of B)`.
6. **Calibration**: per-market `IsotonicRegression` fit on historical
   (predicted, observed) pairs. **Currently gated**: the exporter publishes
   `calibration.applied = false` until at least 3 completed historical races
   are available in the training set. With one completed 2026 round and no
   in-repo multi-season backfill, isotonic on ~22 binary observations per
   market would collapse to a degenerate step function — so the honest answer
   is to publish the raw Plackett-Luce numbers and flag them as uncalibrated.
   The gate flips automatically once the multi-season backfill (audit §2.2 /
   Tier 1) lands; no code change required.

---

## Evaluation metrics

The intended evaluation suite is implemented in `forward_eval.py` and
`models/calibration.py`. Per-round metrics:

- **Position error** (mean / median absolute) — predicted vs actual finishing
  position.
- **Winner hit-rate** — fraction of rounds where the top-probability driver
  actually won.
- **Podium hit-rate** — fraction of predicted top-3 entries actually finishing
  on the podium.
- **Brier score** — per market (`win`, `podium`, `top6`, `top10`).
- **Log-loss** — per market.
- **Reliability diagram** — 10-bin per-market calibration plot, written into
  `website/public/data/probabilities/calibration_summary.json`.

**Honest disclosure (May 2026)**: only Round 4 of 2026 has actual results in
the repo at this time. That single race is statistically insufficient to
report Brier / log-loss with any meaningful confidence interval, so the
calibration summary writes `null` for those metrics when the sample count is
below threshold. Quoted numbers will land once the historical backfill is in.

---

## Known limitations

- **In-race fit, not true train-on-history**: the regression target is
  `AdjustedQualiTime` derived from the current race weekend's qualifying data,
  not a global lap-time model trained out-of-sample. This is great for "who
  is fastest in clean air right now" but underestimates the value of broader
  driver-form trends.
- **Calibration gate at 3+ historical rounds**: isotonic calibration is not
  applied to published probabilities until the gate is satisfied. Multi-season
  backfill of 2023/2024/2025 predictions (with strict leakage discipline) is
  required to flip the gate; this is Tier 1 work and is not yet shipped.
  Edges computed against an uncalibrated model are **directional only, not
  actionable**.
- **DNF and lap-1 chaos not separately modelled**: the model assumes every
  driver finishes; safety-car likelihood is a circuit feature but does not
  feed a discrete "did they finish?" head. Real DNFs make the Monte Carlo
  understate variance.
- **2026 Cadillac team**: brand-new entry with no historical pace; predictions
  for Pérez and Bottas in the Cadillac car are extrapolated from their last
  full-time seasons and a team-change adjustment, with correspondingly higher
  uncertainty for the first ~5 rounds of the season.
- **The Odds API has no F1 coverage**: as of 2026-05 the live-odds ingest path
  cannot pull real prices. `odds_ingest.py` exits with a clear error pointing
  at alternative sources (Pinnacle direct, Betfair Exchange, manual CSV); the
  `/value` page renders its empty state until one of those alternatives is
  wired.
- **Single-season training span in-repo**: the calibration data limitation
  cascades through everything that depends on it (reliability diagrams,
  applied probabilities, backtest metrics). Sharpe / max-drawdown numbers in
  `backtest.py` are deliberately suppressed until `>=5` completed rounds of
  actuals are available.

---

## Ethical considerations

- The `/value` page is a betting tool. It carries a disclaimer
  ("Educational use only; verify with your sportsbook; gambling involves
  loss.") on every export and on the page itself.
- No automated bet placement: the system surfaces opportunities; a human
  decides what to do.
- No underage targeting: the website has no account system and no targeted
  advertising.
- No "tip service" framing: numbers are published with their calibration
  status and known data limitations, not as guarantees.
- Fractional-Kelly sizing (default 0.25× full Kelly) and a portfolio cap
  (5% per bet, 30% total exposure) are baked into `bet_sizing.cap_portfolio`
  so the suggested stakes degrade gracefully under model error.

---

## Reproducibility

- `random_state=42` is pinned in `train_ensemble` (GBR + XGBoost).
- `np.random.default_rng(seed=42)` is the only RNG used in the Plackett–Luce
  sampler; the function takes `seed` as an argument so calibration tests can
  override it.
- `f1_cache/` and `weather_cache/` are gitignored but cached locally; a fresh
  clone re-fetches on demand from FastF1 / OpenMeteo. Cache contents are not
  versioned today (audit §4.6 tracks adding a manifest with checksums).
- Calibration gating threshold (`--min-completed-rounds`, default 3) is a CLI
  flag on `export_probabilities.py`. Reproducing today's exports means using
  the default; do not raise it implicitly.
- The full test suite (`pytest tests/` — 118 tests as of this writing,
  including `test_calibration.py`, `test_leakage.py`, `test_betting.py`,
  `test_forward_eval.py`) must pass green before any export is published.
