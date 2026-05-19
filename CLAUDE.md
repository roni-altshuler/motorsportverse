# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- Conda env name: `f1_predictions` (Python 3.11). The Python interpreter and `pytest` resolve via this env.
- `python-dotenv` auto-loads `.env` from the project root for any module that calls `load_dotenv()`. Optional — code falls back to `os.environ` when dotenv is not installed.
- Full env-var reference: [`docs/ENV_VARS.md`](docs/ENV_VARS.md). The critical ones are `ODDS_API_KEY`, `F1_SEASON_YEAR`, `F1_USE_LIVE_STANDINGS`, and the `BETFAIR_*` triplet.

## Commands

### Python pipeline

```bash
# Run the full ML pipeline for one round (predicts → writes JSON + visualizations)
python export_website_data.py --round 6 --fastf1 --advanced

# Probability layer (Plackett-Luce → isotonic calibration → /value JSON)
python export_probabilities.py                    # all rounds
python export_probabilities.py --rounds 1,2,3     # subset
python export_probabilities.py --min-completed-rounds 5   # raise calibration gate

# Forward-time evaluation (scores predicted vs actual per round)
python forward_eval.py --season 2026

# Historical backfill (populates data/history.duckdb so calibration applies)
python backfill_history.py --seasons 2023,2024,2025 --force
# FastF1 rate-limits at ~500 requests/hour. Expect partial completion;
# re-run later to backfill the rest.

# Standalone per-race entrypoint (auto-generated under races/)
python races/round_06_monaco_gp.py
```

### Odds ingestion (5 paths, same wrapped-payload schema downstream)

```bash
# Unified — auto-selects + merges Betfair + CSV
python odds_ingest_unified.py --round 6 --season 2026 [--merge best-back|average|prefer-betfair|prefer-csv]

# Multi-source scraper — bulk-ingests every CSV in odds_inbox/round_NN*.csv as
# separate bookmakers; optional Oddschecker scrape
python odds_scraper.py --round 6 --season 2026 --scrape oddschecker
python odds_scraper.py --round 6 --season 2026 --ingest-only

# Single-source ingesters (called by the unified/scraper above)
python odds_ingest.py        --round 6 --season 2026   # The Odds API — DOES NOT COVER F1, see below
python odds_ingest_betfair.py --round 6 --season 2026  # requires BETFAIR_* env + betfairlightweight
python odds_import_csv.py     --round 6 --season 2026 --csv odds_inbox/round_06.csv
python odds_import_csv.py     --print-template > odds_inbox/round_06.csv  # 22-driver template

# After odds land, compute edges + Kelly sizing
python export_value_data.py --round 6 --season 2026
```

### Tests & lint

```bash
pytest tests/ -q                            # full suite (218+ tests; ~10s)
pytest tests/test_leakage.py -v             # one file
pytest tests/ -q -k calibration             # filter by keyword
ruff check leakage.py forward_eval.py tests/   # what CI runs
```

### Website (Next.js 16 static export → GitHub Pages)

```bash
cd website
npm install
npm run dev           # http://localhost:3000
npm run build         # runs prebuild (OG image generation via satori) then `next build`
npm run lint          # eslint
```

The website is **static export only** (`output: "export"` in [`next.config.ts`](website/next.config.ts)). No server components, no API routes, no runtime fetches against secrets. All data flows in as JSON at build time from `website/public/data/`.

## Architecture

### Two-layer prediction pipeline

The pipeline has **two unrelated training pathways** that share only the predicted-lap-times output:

1. **Per-race regression model** (`f1_prediction_utils.py::train_ensemble`):
   - Target: `AdjustedQualiTime` (not race finishing time, not position).
   - Per-race fit on 22 drivers: `train_test_split` is splitting *drivers*, not rounds. The "test set" is just 4-5 held-out drivers from the same race. This is *not* a forward-time eval — `forward_eval.py` is.
   - Outputs `PredictedLapTime_GB`, `PredictedLapTime_XGB`, optional `PredictedLapTime_LSTM`, ensemble + RaceProjectionScore in `website/public/data/rounds/round_NN.json::classification[*].predictedTime`.

2. **Probability layer** (`models/calibration.py` + `export_probabilities.py`):
   - Reads `classification[*].predictedTime` from the round JSON.
   - Plackett-Luce sampling via the Gumbel-max trick (5000 MC samples, `np.random.default_rng(seed=42)`) → per-driver `p_win`, `p_podium`, `p_top6`, `p_top10`, plus H2H matrix.
   - Isotonic calibration via `ProbabilityCalibrator.fit_from_history(...)` using `(predicted_p, observed_outcome)` pairs from `data/history.duckdb` (populated by `backfill_history.py`).
   - Output: `website/public/data/probabilities/round_NN.json` + `calibration_summary.json`.

### Calibration is honestly gated

`export_probabilities.py` writes `calibration.applied = false` until the history DB contains ≥ `--min-completed-rounds` distinct (season, round) tuples (default 3). When `applied=false`, raw Plackett-Luce numbers are published as-is and the website renders a disclaimer banner on `/value` and `/accuracy`. The gate exists because isotonic on a tiny sample collapses to a step function. **Never claim calibration is applied without verifying the gate trips.**

### Leakage discipline

`leakage.py` exports `assert_prior_only(rounds_map, current_round, label)`. Every aggregator that touches multi-round history (`_load_season_position_maps`, `_add_dynamic_team_form`, `_add_current_season_form`, `_add_race_to_race_features`, `_add_prediction_bias_features`) must filter to rounds strictly less than `current_round`. The assertion is wired:

- [`f1_prediction_utils.py:build_training_dataset`](f1_prediction_utils.py) rejects non-positive `current_round` at entry.
- [`f1_prediction_utils.py:_load_season_position_maps`](f1_prediction_utils.py) re-asserts after its own filter — defence in depth.
- `backfill_history.py` uses `assert_seasons_prior_only(...)` to forbid training a 2024 prediction on 2024+ data.

If you add a new feature that aggregates prior data, **plumb `current_round` through and assert at the boundary** — don't trust your own filter.

### Odds ingestion: 5 paths because The Odds API has no F1

Discovered 2026-05: The Odds API catalogs 160+ sports, zero motorsport. `odds_ingest.py` now surfaces a `SystemExit` with the alternative-source list on 404. The working paths are:

- **`odds_import_csv.py`** — manual Oddschecker → CSV → `odds_cache/round_NN_<ts>.json`.
- **`odds_ingest_betfair.py`** — Betfair Exchange API via `betfairlightweight` (KYC'd account + free dev key).
- **`odds_ingest_unified.py`** — orchestrates Betfair + CSV in-memory with merge strategies (`auto`, `best-back`, `average`, `prefer-betfair`, `prefer-csv`); writes one combined snapshot.
- **`odds_scraper.py`** — bulk-ingests every `odds_inbox/round_NN*.csv` (filename suffix = bookmaker key) into a multi-bookmaker snapshot; can also run pluggable HTML scrapers (`OddscheckerScraper` etc.).

All five paths write to `odds_cache/round_NN_<timestamp>*.json` in the same wrapped-payload schema that `odds_ingest.parse_winner_odds` consumes. `export_value_data.py::select_bookmaker` then picks Pinnacle > Betfair > … > lowest-overround.

### Website ↔ Python contract

Data flows Python → JSON → TypeScript. The TS interfaces in [`website/src/types/index.ts`](website/src/types/index.ts) are the contract. When you change a Python output, update the matching TS type **in the same change** and update the pydantic mirror in [`tests/test_website_data_schema.py`](tests/test_website_data_schema.py) so CI gates breakage. The pydantic models use `extra="ignore"` (permissive on additions, strict on the load-bearing required fields).

Key data files under `website/public/data/`:

- `season.json` — calendar, drivers, teams, completed rounds.
- `rounds/round_NN.json` — predicted classification, model metrics, visualizations list.
- `probabilities/round_NN.json` + `calibration_summary.json` — probability layer outputs.
- `value/round_NN.json` — edges + Kelly sizing for the `/value` page.
- `standings.json`, `season_tracker.json`, `gp_accuracy_report.json`, `weather.json`.

### CI gates

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — `ruff check` + full `pytest tests/` on every push/PR.
- [`.github/workflows/update_predictions.yml`](.github/workflows/update_predictions.yml) — cron-scheduled race-weekend pipeline. After it generates new JSON, it runs **`pytest tests/test_website_data_schema.py tests/test_predictions_sanity.py`** against the freshly-generated data *before* committing — this is the gate that stops degenerate output (all-NaN, missing drivers, duplicate positions) from reaching GitHub Pages.

### Subagents available

Four project-specific subagents live in [`.claude/agents/`](.claude/agents/). Invoke via `Agent(subagent_type="<name>", ...)`:

- **f1-ml-core** — model training, CV, leakage, calibration, Monte Carlo race-sim, hyperparameter tuning. Owns `f1_prediction_utils.py`, `advanced_models.py`, `models/`, `export_probabilities.py`, `backfill_history.py`.
- **f1-betting-quant** — odds ingestion, Kelly sizing, backtest engine. Owns `odds_*.py`, `bet_sizing.py`, `backtest.py`, `export_value_data.py`.
- **f1-website-dev** — Next.js pages, SEO, accessibility, edge UI. Owns `website/`.
- **f1-eng-quality** — tests, CI, refactor, dependency pinning, module splitting. Owns `tests/`, `.github/workflows/`, `requirements*.txt`.

Note: these agent definitions are read from disk at session start, so a newly-added subagent only becomes available in the next session.

## Project gotchas to remember

- **The model target is `AdjustedQualiTime`, not race finishing position.** The race ranking is a post-processing step (`RaceProjectionScore`) — see `f1_prediction_utils.py` around line 1100. Don't refactor as if it were a position-regression model.
- **FastF1 rate-limits at 500 requests/hour.** Backfill of 2023+2024+2025 typically tops out at ~24-30 rounds per run; re-run later to fill in the rest. The DB is idempotent (PK on `(season, round, driver)`).
- **`.gitignore` patterns are anchored with care.** `/data/` is anchored to the project root (it's the DuckDB directory) and does **not** match `website/public/data/`. Don't add unanchored `data/` — that silently blocks website JSON commits.
- **Inline comments in `.gitignore` are part of the pattern.** Put `#` comments on their own line.
- **Long roadmap context** lives in [`/home/roaltshu/.claude/plans/hi-i-have-a-iridescent-pebble.md`](../.claude/plans/hi-i-have-a-iridescent-pebble.md) (Tier 0–4 audit). Refer there for "why does X look the way it does" questions before refactoring.
