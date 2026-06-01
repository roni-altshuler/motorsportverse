# Development guide

## One-time setup

```bash
# 1. Clone the repo
git clone https://github.com/roni-altshuler/f1_predictions.git
cd f1_predictions

# 2. Create the Python env (3.11 recommended)
conda create -n f1_predictions python=3.11 -y
conda activate f1_predictions

# 3. Install Python deps
pip install -r requirements.txt
pip install -r requirements-dev.txt  # adds pytest, ruff, etc.

# 4. Install website deps
cd website
npm install   # honours .npmrc: legacy-peer-deps=true
cd ..

# 5. (Optional) Register a Jupyter kernel
pip install ipykernel
python -m ipykernel install --user --name f1_predictions --display-name "Python (F1 Predictions)"
```

## Environment variables

Full reference in [`docs/ENV_VARS.md`](ENV_VARS.md). Critical ones:

| Variable | Default | Purpose |
|---|---|---|
| `F1_SEASON_YEAR` | `2026` | Which season's predictions to publish |
| `F1_USE_LIVE_STANDINGS` | `1` | Pull official standings from Jolpica on each export |
| `F1_USE_LIVE_ROUND_RESULTS` | `1` | Refresh `actualResults` from official classified results when a round completes |
| `F1_REGISTRY_ENABLED` | `1` | Set `0` to make the model registry a logged no-op (useful for tests) |
| `ODDS_API_KEY` | — | Optional, for the dormant betting flow |

`python-dotenv` auto-loads `.env` from the project root. Falls back to `os.environ` when dotenv is unavailable.

## Day-to-day commands

### Python pipeline

```bash
# Predict + export one round (full pipeline)
python export_website_data.py --round 6 --fastf1 --advanced

# Opt into the per-lap race simulator
python export_website_data.py --round 6 --use-race-simulator

# Probability layer (Plackett-Luce → calibration)
python export_probabilities.py --rounds 1,2,3,4,5,6

# Forward-time evaluation
python forward_eval.py --season 2026 --per-round-dir website/public/data/forward_eval --allow-empty

# Drift report
python drift_report.py --season 2026 --allow-empty

# Promotion decision
python promotion_decision.py --season 2026 --allow-empty

# Historical backfill
python backfill_history.py --seasons 2023,2024,2025 --force      # Tier 1 (FastF1, rate-limited)
python ergast_backfill.py --seasons 1950-2025                    # Tier 2 (Ergast/Jolpica, no rate cap)

# Offline trainer for the per-lap race simulator
python train_race_pace.py --seasons 2018-2025
```

### Website

```bash
cd website

npm run dev        # http://localhost:3000
npm run build      # runs prebuild (OG images + PNG→WebP) then `next build`
npm run lint       # ESLint
npm run webp       # one-shot regenerate .webp siblings under public/visualizations/
```

The site is **static-export only** (`output: "export"` in [`next.config.ts`](../website/next.config.ts)). No server components, no API routes, no runtime secret fetches. All data flows in as JSON at build time from `website/public/data/`.

### Tests + lint

```bash
pytest tests/ -q                            # full suite (390+ tests; ~15s)
pytest tests/test_leakage.py -v             # one file
pytest tests/ -q -k calibration             # filter by keyword
ruff check .                                # what CI runs (config in pyproject.toml)
```

## Build gotchas

### `npm run prebuild` regenerates `.webp` siblings every time

[`scripts/convert-viz-to-webp.ts`](../website/scripts/convert-viz-to-webp.ts) (sharp-based, idempotent in content but **not byte-deterministic**) regenerates WebP encodings of PNGs under `public/visualizations/`. After every local build you'll see modified `.webp` files in `git status` even when nothing logically changed.

Two options:
1. Commit the regenerated WebPs as a `chore(viz): regenerate webp siblings` commit (current pattern).
2. Add the WebP files to `.gitignore` and let CI regenerate them on deploy. This avoids the noise but means local devs see a slower first-build.

### `legacy-peer-deps=true` in `.npmrc`

`@visx/*` declares its React peer as `^16–18` but we run React 19. The [`website/.npmrc`](../website/.npmrc) pin lets `npm ci` succeed on CI. Do **not** delete it.

### `gsap` + `framer-motion` must not share a DOM node

Rule: framer-motion owns entrance/exit (mount, route change, accordion open). GSAP owns scroll-tied effects (path-draw, parallax, the track-map orange sweep). Never bind both to the same node; if a node needs both, GSAP wins and framer-motion stays opacity-only there.

### `data/history.duckdb` gitignore subtlety

The `.gitignore` rule `/data/` is **project-root-anchored** and does NOT match `website/public/data/`. Do not add an unanchored `data/` pattern — it would silently block website JSON commits.

## Deploy

### GitHub Pages
[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) builds `website/` and publishes the static export. `PAGES_BASE_PATH` sets the basePath if deploying to a subdirectory.

### Continuous data refresh
[`.github/workflows/update_predictions.yml`](../.github/workflows/update_predictions.yml) — cron-scheduled race-weekend pipeline. Runs `gp_weekend.py`, then `forward_eval.py --per-round-dir ... --allow-empty`, then `drift_report.py --allow-empty`, then `promotion_decision.py --allow-empty`, then `pytest tests/test_website_data_schema.py tests/test_predictions_sanity.py` *before* committing. The pytest is the gate that stops degenerate output (all-NaN, missing drivers, duplicate positions) from reaching GitHub Pages.

### Historical backfill cron
[`.github/workflows/backfill_history.yml`](../.github/workflows/backfill_history.yml) — nightly cron at 03:00 UTC. Runs Ergast (Tier 2), then a rate-limited slice of FastF1 (Tier 1), then force-commits `data/history.duckdb` if changed.

## Project subagents

Four project-specific Claude Code subagents live in [`.claude/agents/`](../.claude/agents/). Invoke via `Agent(subagent_type="<name>", ...)`. Note: agent definitions are read at session start, so a new subagent only becomes available in the next session.

- **f1-ml-core** — model training, CV, leakage, calibration, Monte Carlo race-sim, hyperparameter tuning.
- **f1-betting-quant** — odds ingestion, Kelly sizing, backtest engine.
- **f1-website-dev** — Next.js pages, SEO, accessibility.
- **f1-eng-quality** — tests, CI, refactor, dependency pinning, module splitting.

If the worktree-isolation mode is enforced and the user's working directory isn't itself a git repo, agent dispatch will fail with `Cannot create agent worktree: not in a git repository`. Fall back to executing directly as the main agent.
