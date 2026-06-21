# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Conda env name: `f1_predictions` (Python 3.11). The Python interpreter and `pytest` resolve via this env.
- `python-dotenv` auto-loads `.env` from the project root for any module that calls `load_dotenv()`. Optional — code falls back to `os.environ` when dotenv is not installed.
- Full env-var reference: [`docs/ENV_VARS.md`](docs/ENV_VARS.md). The critical ones are `ODDS_API_KEY`, `F1_SEASON_YEAR`, `F1_USE_LIVE_STANDINGS`, and the `BETFAIR_*` triplet. Two newer toggles: `F1_REGISTRY_ENABLED` (default `"1"`; setting `"0"` makes the model registry a logged no-op for tests) and `F1_USE_LIVE_ROUND_RESULTS` (default `"1"`).

## Commands

### Python pipeline

```bash
# Run the full ML pipeline for one round (predicts → writes JSON + visualizations)
python src/export_website_data.py --round 6 --fastf1 --advanced

# Opt into the per-lap Monte Carlo race simulator (A-P1.1 Step 3).  Silently
# no-ops when no race-pace ensemble is registered — run train_race_pace.py first.
python src/export_website_data.py --round 6 --use-race-simulator

# Probability layer (Plackett-Luce → isotonic calibration → /value JSON)
python src/export_probabilities.py                    # all rounds
python src/export_probabilities.py --rounds 1,2,3     # subset
python src/export_probabilities.py --min-completed-rounds 5   # raise calibration gate

# Forward-time evaluation (scores predicted vs actual per round)
python src/forward_eval.py --season 2026
python src/forward_eval.py --season 2026 --per-round-dir website/public/data/forward_eval --allow-empty

# Drift report (feature PSI + rolling Brier) → model_health.json
python src/drift_report.py --season 2026 --allow-empty

# Shadow / A-B promotion decision (production vs candidate stream)
python src/promotion_decision.py --season 2026 --allow-empty

# Historical backfill (populates data/history.duckdb so calibration applies)
python src/backfill_history.py --seasons 2023,2024,2025 --force      # Tier 1 (FastF1)
python src/ergast_backfill.py --seasons 1950-2025                    # Tier 2 (Jolpica/Ergast)

# Offline trainer for the per-lap race-pace ensemble (saves to registry)
python src/train_race_pace.py --seasons 2018-2025
```

FastF1 rate-limits at ~500 requests/hour. The Tier-1 backfill typically tops out at ~24-30 rounds per run; re-run later to fill the rest. The DB is idempotent (PK on `(season, round, driver)`).

### Odds ingestion (5 paths, same wrapped-payload schema downstream)

```bash
python src/odds_ingest_unified.py --round 6 --season 2026 [--merge best-back|average|prefer-betfair|prefer-csv]
python src/odds_scraper.py --round 6 --season 2026 --scrape oddschecker
python src/odds_ingest.py        --round 6 --season 2026   # The Odds API — DOES NOT COVER F1, see below
python src/odds_ingest_betfair.py --round 6 --season 2026  # requires BETFAIR_* env + betfairlightweight
python src/odds_import_csv.py     --round 6 --season 2026 --csv odds_inbox/round_06.csv
python src/odds_import_csv.py     --print-template > odds_inbox/round_06.csv  # 22-driver template

# After odds land, compute edges + Kelly sizing
python src/export_value_data.py --round 6 --season 2026
```

The `/value` page was removed from the website in the 2026-05-21 redesign. The Python-side odds-ingest CLIs above remain — they're backend tooling for a future revival of the betting flow.

### Tests & lint

```bash
pytest tests/ -q                            # full suite (390+ tests; ~15s)
pytest tests/test_leakage.py -v             # one file
pytest tests/ -q -k calibration             # filter by keyword
ruff check .                                   # what CI runs (config in pyproject.toml)
```

### Website (Next.js 16 static export → GitHub Pages)

```bash
cd website
npm install           # honours website/.npmrc (legacy-peer-deps=true)
npm run dev           # http://localhost:3000
npm run build         # runs prebuild (OG images + PNG→WebP) then `next build`
npm run lint          # eslint
npm run webp          # one-shot: regenerate .webp siblings under public/visualizations/
```

The website is **static export only** (`output: "export"` in [`next.config.ts`](website/next.config.ts)). No server components, no API routes, no runtime fetches against secrets. All data flows in as JSON at build time from `website/public/data/`.

**[`website/.npmrc`](website/.npmrc) pins `legacy-peer-deps=true`** so `npm ci` succeeds on CI. `@visx/*` declares its React peer as `^16–18` but the project runs on React 19; the npmrc lets the install resolve. Do **not** delete it.

## Architecture

### Three-layer prediction pipeline

The pipeline now has **three pathways**. The first two share only the predicted-lap-times output; the third is opt-in and replaces the qualifying-time post-processing with a learned race simulator.

1. **Per-race regression model** ([`f1_prediction_utils.py::train_ensemble`](f1_prediction_utils.py)):
   - Target: `AdjustedQualiTime` (not race finishing time, not position).
   - Per-race fit on 22 drivers: `train_test_split` is splitting *drivers*, not rounds. The "test set" is just 4-5 held-out drivers from the same race. This is *not* a forward-time eval — `forward_eval.py` is.
   - Outputs `PredictedLapTime_GB`, `PredictedLapTime_XGB`, optional `PredictedLapTime_LSTM`, ensemble + `RaceProjectionScore`, plus **A-P2.3 bootstrap intervals** (`PredictedLapTimeLow` / `High`) in `website/public/data/rounds/round_NN.json::classification[*]`.

2. **Probability layer** ([`models/calibration.py`](models/calibration.py) + [`export_probabilities.py`](export_probabilities.py)):
   - Reads `classification[*].predictedTime` from the round JSON.
   - Plackett-Luce sampling via the Gumbel-max trick (5000 MC samples, `np.random.default_rng(seed=42)`) → per-driver `p_win`, `p_podium`, `p_top6`, `p_top10`, plus H2H matrix.
   - Isotonic calibration via `ProbabilityCalibrator.fit_from_history(...)` using `(predicted_p, observed_outcome)` pairs from `data/history.duckdb`. **`StratifiedProbabilityCalibrator`** (A-P2.2) extends this with per-(market, stratum) fits and a global fallback.
   - Output: `website/public/data/probabilities/round_NN.json` + `calibration_summary.json`.

3. **Per-lap Monte Carlo race simulator** ([`models/race_pace.py`](models/race_pace.py) + [`models/race_simulator.py`](models/race_simulator.py) + [`models/race_simulator_runner.py`](models/race_simulator_runner.py)):
   - Per-lap GBR + XGB ensemble on lap-by-lap race telemetry; 16-feature catalogue (driver/team/circuit ids, lap_number, lap_progress, track_position, tyre_compound_code, tyre_age_laps, gap_to_car_ahead/behind, sc/vsc/yellow flags, air/track temp, rain_intensity).
   - Simulator iterates `predict_lap_times` per driver per lap, maintains running gaps + positions, samples pit-stop laps, injects SC events from a Poisson process. Default 2000 MC samples.
   - Trained offline via `train_race_pace.py`; persisted under `models/registry/<season>_round_99/` (sentinel round 99) with `metadata.kind=="race-pace"`.
   - Opt-in via `--use-race-simulator` on `export_website_data.py`. When active, splices `simulatorWinProbability` / `simulatorPodiumProbability` / `simulatorTop6Probability` / `simulatorTop10Probability` / `simulatorMeanFinish` into each classification entry plus a `modelConfig.raceSimulator` block. Silently no-ops when no race-pace ensemble has been registered.

### Continuous-learning infrastructure

Each piece writes to `website/public/data/` and is wired into [`update_predictions.yml`](.github/workflows/update_predictions.yml) so the race-weekend cron exercises the full loop.

- **[`models/registry.py`](models/registry.py)** — file-backed model registry. `ModelRegistry().save(season, round_num, models, metadata)` writes joblib/torch artefacts plus `metadata.json` under `models/registry/<season>_round_<NN>/`. Round range is 1..99: 1..30 covers real F1 calendars; 31..99 is reserved for sentinel entries (race-pace = 99; game-theory coefficients = 98). Binaries are gitignored; `metadata.json` is committed.
- **[`forward_eval.py`](forward_eval.py)** — per-round metrics (MAE, Brier-vs-uniform, Spearman, NDCG@5) + a `last_race_winner` baseline. CLI flags `--per-round-dir` (writes `forward_eval/round_NN.json` files) and `--allow-empty` (exit 0 on pre-race phases).
- **[`models/drift.py`](models/drift.py)** + **[`drift_report.py`](drift_report.py)** — PSI per feature against a baseline + rolling-Brier trend. Severity bands: PSI 0.10/0.25, Brier 5%/15% regression. Output: `model_health.json` with warnings + alarms.
- **[`models/promotion.py`](models/promotion.py)** + **[`promotion_decision.py`](promotion_decision.py)** — guarded production/candidate comparison. Requires ≥5 overlapping rounds + 2% mean improvement + no per-round 20%+ regression before recommending promote. Output: `promotion_status.json`.
- **[`models/online_game_theory.py`](models/online_game_theory.py)** — ridge-regression learner for the 7 game-theory coefficients in `RaceProjectionScore`. Exponential blend with the legacy values (default α=0.30, ~2-round half-life). Registry sentinel round 98.

### Accuracy metric & post-race data hydration

Two pieces of post-race logic are easy to get wrong because the data flows through
two parallel code paths that **must stay identical**:

- **Headline accuracy** is a **podium-weighted classification blend**, NOT
  "within-N positions". [`advanced_models.py::podium_points_accuracy`](advanced_models.py)
  is the single source of truth: `0.6 * podium% + 0.4 * points%`, where each term
  is *set-membership* overlap — how many of the actual top-3 / top-10 drivers the
  model also placed in that group (exact P1/P2/P3 order within the group does NOT
  matter). It's consumed by both `SeasonTracker._compute_accuracy` (feeds
  `season_tracker.json`, the navbar chip, the accuracy dashboard) **and**
  `export_website_data._compute_round_accuracy` (feeds `round_NN.json::accuracy`).
  If you change the formula, change the helper, not the call sites. The legacy
  `within_3_positions` / `*_classified` fields are still computed but are
  transparency detail only — `accuracy_pct` is the blend.
- **Weekend race-session timing** can lag the classified order. A concluded race
  whose Jolpica `results` fetch was empty at export time would otherwise show
  "Awaiting data". [`export_website_data._refresh_race_session_timing`](export_website_data.py)
  re-fetches from Jolpica (timing usually publishes shortly after the order) and
  only falls back to `_backfill_race_session_from_actual` (position-only synthesis
  from `actualResults`, no times/grid/laps) when nothing is published yet. Both are
  self-healing and wired into `export_round_data`, so a normal re-export fixes a
  stranded session.

**Recomputing past rounds WITHOUT re-prediction:** predictions are locked once a
weekend runs — never re-run the ML predictor over a completed round to refresh
derived data. [`diagnostics/recompute_accuracy_podium_points.py`](diagnostics/recompute_accuracy_podium_points.py)
is the pattern: `SeasonTracker.sync_from_round_directory` recomputes accuracy from
the stored `predicted`/`actual`, re-publishes `season_tracker.json` +
`gp_accuracy_report.json`, and writes the recomputed `accuracy` block back into
each `round_NN.json` — all without touching `classification`.

The home page only shows the "Predicted Podium — Next Grand Prix" forecast once
that round's qualifying session is `official` ([`HomePage.tsx`](website/src/components/HomePage.tsx))
— the model has no genuine forecast before qualifying, so don't tease one.

### Calibration is honestly gated

`export_probabilities.py` writes `calibration.applied = false` until the history DB contains ≥ `--min-completed-rounds` distinct (season, round) tuples (default 3). When `applied=false`, raw Plackett-Luce numbers are published as-is and the website renders a disclaimer banner. The gate exists because isotonic on a tiny sample collapses to a step function. **Never claim calibration is applied without verifying the gate trips.**

### Leakage discipline

[`leakage.py`](leakage.py) exports `assert_prior_only(rounds_map, current_round, label)` and `assert_seasons_prior_only(...)`. Every aggregator that touches multi-round history must filter to rounds strictly less than `current_round`. The assertion is wired at the boundary in [`f1_prediction_utils.py::build_training_dataset`](f1_prediction_utils.py) and inside `_load_season_position_maps`; both `backfill_history.py` and `ergast_backfill.py` use the multi-season variant.

If you add a new feature that aggregates prior data, **plumb `current_round` through and assert at the boundary** — don't trust your own filter.

### Visualisation styling

[`viz_style.py`](viz_style.py) is the central matplotlib design system — `apply_viz_style()` is called automatically on import and sets graphite surfaces (`VIZ_COLORS["bg"]` = `#0E1116`) + telemetry orange (`#F76B15`) as the single accent. Every PNG generator (`export_website_data.py::_export_visualizations`, `generate_fastf1_viz.py`, `f1_prediction_utils.py`) imports from `viz_style` so the entire chart catalogue stays in sync. Per-axis conventions live in `style_axis(ax, ...)`.

**Curated chart set** (2026-05-21 cull, from 17 → 6): `predicted_laptimes`, `laptime_distribution`, `podium_probability_board`, `finish_probability_heatmap`, `head_to_head_edges`, `track_map`. The Python PNG generators still run (used for the lightbox-able circuit figure, social-share OG assets, and as fallback inside `<ChartContainer>`). **The website's primary chart surface is now interactive React (recharts + visx)** — see [`website/src/components/charts/`](website/src/components/charts/). When you add a new chart, add the React component there; only add a matplotlib generator if you also need a static export (OG, lightbox, etc.).

### Odds ingestion: 5 paths because The Odds API has no F1

The Odds API catalogs 160+ sports, zero motorsport. `odds_ingest.py` surfaces a `SystemExit` with the alternative-source list on 404. The working paths are:

- **[`odds_import_csv.py`](odds_import_csv.py)** — manual Oddschecker → CSV → `odds_cache/round_NN_<ts>.json`.
- **[`odds_ingest_betfair.py`](odds_ingest_betfair.py)** — Betfair Exchange API via `betfairlightweight` (KYC'd account + free dev key).
- **[`odds_ingest_unified.py`](odds_ingest_unified.py)** — orchestrates Betfair + CSV in-memory with merge strategies; writes one combined snapshot.
- **[`odds_scraper.py`](odds_scraper.py)** — bulk-ingests every `odds_inbox/round_NN*.csv` (filename suffix = bookmaker key) into a multi-bookmaker snapshot; optional pluggable HTML scrapers.

All five paths write to `odds_cache/round_NN_<timestamp>*.json` in the same wrapped-payload schema that `odds_ingest.parse_winner_odds` consumes. `export_value_data.py::select_bookmaker` then picks Pinnacle > Betfair > … > lowest-overround. The `/value` website page was removed in the 2026-05-21 redesign; these are backend-only for now.

### Website ↔ Python contract

Data flows Python → JSON → TypeScript. The TS interfaces in [`website/src/types/index.ts`](website/src/types/index.ts) are the contract. When you change a Python output, update the matching TS type **in the same change** and update the pydantic mirror in [`tests/test_website_data_schema.py`](tests/test_website_data_schema.py) so CI gates breakage. The pydantic models use `extra="ignore"` (permissive on additions, strict on the load-bearing required fields).

Key data files under `website/public/data/`:

- `season.json` — calendar, drivers, teams, completed rounds.
- `rounds/round_NN.json` — predicted classification + bootstrap intervals + optional simulator probabilities, model metrics, visualizations list, weather, strategy data.
- `probabilities/round_NN.json` + `calibration_summary.json` — probability layer outputs.
- `standings.json`, `season_tracker.json`, `weather.json`.
- `forward_eval/round_NN.json` — per-round accuracy metrics (A-P0.2).
- `model_health.json` — feature drift + rolling-Brier (A-P1.2).
- `promotion_status.json` — shadow/A-B promotion decision (A-P1.3).
- `gp_accuracy_report.json` — season-rolling accuracy (used by the navbar accuracy chip). `seasonAccuracyPct` is the podium-weighted classification blend (see "Accuracy metric & post-race data hydration").

### Website design system (cinematic overhaul, supersedes 2026-05 flat redesign)

Aesthetic direction: broadcast-HUD + paddock-badge-wall vocabulary blending F1 TV timing graphics, F1 24 game UI, modern F1.com, and pit-wall analyst console. Dark theme is primary; light theme inherits structure but skips the lighting effects.

- **Tokens** in [`website/src/styles/tokens.css`](website/src/styles/tokens.css): HUD palette (`--hud-purple/yellow/red-light/cyan/champagne`), glow stack (`--glow-accent/podium/team/elevated/hud`), gradient stops (`--gradient-paddock/hud-frame/scanline`), motion tokens (`--dur-*`, `--ease-*`), and an 11-team palette resolved via `[data-team="..."]` attribute or inline `style={{ "--team-color": ... }}`. The cinematic styles **supersede** the 2026-05 flat design — gradients, glow, shadows, and parallax are intentional now.
- **Motion lib** in [`website/src/lib/motion.ts`](website/src/lib/motion.ts) (durations + easings + framer-motion variants), [`useReducedMotion.ts`](website/src/lib/useReducedMotion.ts), [`motionGuard.ts`](website/src/lib/motionGuard.ts), [`useGSAPScrollTrigger.ts`](website/src/lib/useGSAPScrollTrigger.ts) (lazy GSAP import gated on `prefers-reduced-motion`). Every effect has a reduced-motion equivalent — there's a global `@media (prefers-reduced-motion: reduce)` block in [`globals.css`](website/src/app/globals.css) that short-circuits animations and a hook-based JS path. **Don't ship an effect without a reduced-motion fallback.**
- **Primitives** under [`website/src/components/ui/`](website/src/components/ui/): `Card` (with `surface: flat | glow | hud | paddock` variants), `Badge`, `Button`, `Stat`, `AnimatedNumber` (spring counter), `TeamColorBar`, `HUDPanel` (telemetry frame with optional `scanlines` + `cornerNotch`), `SectorBadge`, `RaceLightsGrid` (lights-out reveal state machine), `LoadingTire` (SVG tire spinner). `cn()` helper for class merging. There is no real `@radix-ui/react-slot` install; do NOT use `<Button asChild>`. Use `buttonVariants({...})` as a className on `<Link>` instead.
- **New deps**: `gsap` + `gsap/ScrollTrigger`, `lenis` (smooth scroll, wired via [`SmoothScrollProvider`](website/src/components/SmoothScrollProvider.tsx) in `layout.tsx`), `lottie-react` (reserved for future Lottie assets), `@visx/*` (custom charts beyond recharts). All four are lazy-loaded — never top-level-import `gsap` in a page module or static export breaks.
- **`/design-system`** route showcases every primitive — internal QA surface, not in the nav.
- **Race detail page** has exactly **2 tabs**: "Weekend Sessions" + "Deep Dive". Deep Dive uses native `<details>`/`<summary>` (styled via `.deep-dive-section`) for Model Forecast / Circuit & Telemetry / Strategy / Visualisations. The legacy `Tab` union still carries the old values for type-safety; the UI only routes through "weekend" and "deepdive". **Inside Deep Dive > Visualisations, only the new interactive React charts render** — `FinishProbabilityHeatmap`, `HeadToHeadMatrix`, `LapTimeDistributionChart` from [`website/src/components/charts/`](website/src/components/charts/). The legacy PNG `viz-command-center` + `viz-workbench` + per-category grids were removed; do not re-introduce mixed-style PNG galleries.
- **Track-map figure** is mounted via [`TrackMapWithOverlay`](website/src/components/race-detail/TrackMapWithOverlay.tsx) (HUDPanel frame, vignette, scanline, scroll-tied orange sweep, image filter for contrast). The raw `<Image src={track_map.png}>` is **not** acceptable on its own — it reads as a matplotlib export. Always frame circuit figures through HUDPanel or a similarly-styled wrapper.
- **Navbar Races dropdown** opens on hover (mouseenter on the wrapper div), closes on mouseleave with a ~140ms grace timeout (so the cursor can travel from the trigger button to the menu body). Click still toggles for touch/keyboard, and clicking any race link closes the menu immediately. Don't revert to click-only — it was an explicit UX ask.
- **PNG visualizations still ship** as `<picture>` WebP+PNG siblings. `npm run prebuild` runs `convert-viz-to-webp.ts` (sharp-based, idempotent). The PNGs are still used for: (1) social-share OG images, (2) the lightbox modal, (3) the framed circuit figure on race detail. They are **not** the canonical chart surface anymore.
- **Tech-stack scrub policy**: user-facing pages must not name implementation details (Plackett-Luce, Monte-Carlo, XGBoost, isotonic regression, gradient boosting, etc.). Talk about what the model says, not how it's built. Implementation details belong in [`README.md`](README.md). The About page is product-focused.

### CI gates

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — `ruff check .` (config + per-file ignores in [`pyproject.toml`](pyproject.toml)) + full `pytest tests/` on every push/PR. The whole repo is now linted (excluding generated `races/` scripts, the legacy framework, and `scripts/archive/`).
- [`.github/workflows/update_predictions.yml`](.github/workflows/update_predictions.yml) — cron-scheduled race-weekend pipeline. Runs `gp_weekend.py`, then `forward_eval.py --per-round-dir ... --allow-empty`, then `drift_report.py --allow-empty`, then `promotion_decision.py --allow-empty`, then `pytest tests/test_website_data_schema.py tests/test_predictions_sanity.py` *before* committing. The pytest is the gate that stops degenerate output (all-NaN, missing drivers, duplicate positions) from reaching GitHub Pages.
- [`.github/workflows/backfill_history.yml`](.github/workflows/backfill_history.yml) — nightly cron at 03:00 UTC. Runs the Ergast (Tier 2) backfill, then a rate-limited slice of the FastF1 (Tier 1) backfill, then force-commits `data/history.duckdb` if changed. The DB is gitignored (`/data/`) so the commit step uses `git add -f`.
- The reusable-workflow reference in `update_predictions.yml` uses the absolute form `roni-altshuler/f1_predictions/.github/workflows/deploy.yml@main` (not relative) to keep the VS Code GitHub Actions extension's "Unable to find reusable workflow" diagnostic from firing.

### Subagents available

Four project-specific subagents live in [`.claude/agents/`](.claude/agents/). Invoke via `Agent(subagent_type="<name>", ...)`. Note: these agent definitions are read from disk at session start, so a newly-added subagent only becomes available in the next session.

- **f1-ml-core** — model training, CV, leakage, calibration, Monte Carlo race-sim, hyperparameter tuning. Owns `f1_prediction_utils.py`, `advanced_models.py`, `models/`, `export_probabilities.py`, `backfill_history.py`, `train_race_pace.py`, `forward_eval.py`, `drift_report.py`, `promotion_decision.py`.
- **f1-betting-quant** — odds ingestion, Kelly sizing, backtest engine. Owns `odds_*.py`, `bet_sizing.py`, `backtest.py`, `export_value_data.py`.
- **f1-website-dev** — Next.js pages, SEO, accessibility, edge UI. Owns `website/`.
- **f1-eng-quality** — tests, CI, refactor, dependency pinning, module splitting. Owns `tests/`, `.github/workflows/`, `requirements*.txt`.

If the worktree-isolation mode is enforced by the harness and the user's working directory isn't itself a git repo (only `f1_predictions/` is), agent dispatch will fail with `Cannot create agent worktree: not in a git repository`. Fall back to executing directly as the main agent.

## Project gotchas to remember

- **The qualifying-time model target is `AdjustedQualiTime`, not race finishing position.** The race ranking is a post-processing step (`RaceProjectionScore`) in `f1_prediction_utils.py` around line 1100. The race-pace simulator (model #3) replaces that post-processing when `--use-race-simulator` is set and a trained ensemble is registered.
- **FastF1 rate-limits at 500 requests/hour.** Backfill of 2018-2025 typically tops out at ~24-30 rounds per run; re-run later to fill the rest. Both `backfill_history.py` and `train_race_pace.py` degrade gracefully when the limit is hit.
- **`.gitignore` patterns are anchored with care.** `/data/` is anchored to the project root (it's the DuckDB directory) and does **not** match `website/public/data/`. Don't add unanchored `data/` — that silently blocks website JSON commits. The model registry binaries (`models/registry/**/*.joblib`, `**/*.pt`) are gitignored; `metadata.json` IS committed.
- **Inline comments in `.gitignore` are part of the pattern.** Put `#` comments on their own line.
- **`/value` and `/accuracy` are no longer in the navbar.** Both routes still exist in the static export for inbound links; `/value` will 404-ish on the empty state (no odds data ships); `/accuracy` is functional but surfaced contextually via the navbar accuracy chip rather than a dedicated nav link.
- **`requirements-dev.txt` defers `mapie`, `mlflow`, `optuna`** — they're commented out because `mapie 0.9.2` pulls `scikit-learn<1.6` which conflicts with the `scikit-learn~=1.8.0` runtime pin. Re-enable per package when the consuming feature lands and pick a sklearn-1.8-compatible version.
- **The `pre-existing` ruff F401 warnings in unused test imports** are not lint errors any more — they were cleaned up in the redesign sprint. New unused imports DO fail CI now.
- **Long roadmap context** lives in [`/home/ronaltshuler/.claude/plans/f1-predictions-is-a-github-logical-snowflake.md`](../.claude/plans/f1-predictions-is-a-github-logical-snowflake.md). The top of that file is the *current* sprint plan; everything below `> Earlier sprint plan archived below for historical context.` is historical reference.
- **Animation orchestration discipline.** GSAP and framer-motion can collide on the same DOM node. Rule: framer-motion owns entrance/exit (mount, route change, accordion open). GSAP owns scroll-tied effects (path-draw, parallax, the track-map orange sweep). Never bind both to the same node; if a node needs both, GSAP wins and framer-motion stays opacity-only there.
- **Hero parallax**: the home page's [`HeroParallax`](website/src/components/home/HeroParallax.tsx) uses a CSS-only radial-gradient backdrop by default. Earlier iterations ghosted the matplotlib track map at low opacity behind the hero — that was explicitly rejected as looking too "vanilla and matplotlib". Don't pass `trackImage` to `HeroParallax` from the home page; leave it off so the gradient takes over.
- **`<ChartContainer>`** ([`website/src/components/charts/ChartContainer.tsx`](website/src/components/charts/ChartContainer.tsx)) is the lazy hydration boundary for visx-heavy charts: it shows the PNG/WebP fallback until an IntersectionObserver fires, then crossfades to the React chart. Reuse it for any new chart that ships a PNG fallback — it eliminates CLS during hydration.
- **Calendar race-art URL discipline.** [`website/src/lib/raceArt.ts`](website/src/lib/raceArt.ts) hot-links to Wikimedia Commons (via CSS `background-image`, so `next.config.ts` `remotePatterns` doesn't gate it). **Every URL must be live-verified before committing** — guessed Wikimedia thumbnail filenames almost always 404 (different filename casing, missing `/thumb/` segment, wrong size suffix). To swap an image: query `https://en.wikipedia.org/api/rest_v1/page/media-list/<title>` for JPGs, then `curl -I` the candidate URL. The user explicitly wants aerial circuit photography (Planet Labs SkySat aerials work great), NOT SVG layout diagrams, logos, or generic country landscapes.
- **Driver headshot synthesis.** [`DriverPortrait`](website/src/components/standings/DriverPortrait.tsx) synthesizes `/headshots/<CODE>.webp` when `headshotUrl` is null/missing in the JSON — so `standings.json` does NOT need a `headshotUrl` field per-driver. The `onError` handler falls through to the conic-gradient avatar for reserves or drivers without a `.webp` under [`public/headshots/`](website/public/headshots/). If you add a new driver mid-season, drop the `.webp` in that directory and it appears automatically.
- **Standings points-progression forecast.** [`website/src/lib/standingsForecast.ts`](website/src/lib/standingsForecast.ts) is the pure helper that powers the dashed projection lines past the live cursor in [`StandingsChart`](website/src/components/charts/StandingsChart.tsx). v1 is a linear `points / completed_rounds` pace projection — honest but naive. v2 (flagged `// TODO(v2)` in the helper) should source per-round win/podium probabilities from `probabilities/round_NN.json` and compute `Σ p_position × position_points`. The user-facing label is "Projected at current pace" — do NOT promote to "Model forecast" until v2 ships, because that overclaims under the tech-stack scrub policy.
