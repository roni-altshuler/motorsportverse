# RaceIQ — Setup & onboarding

This is the fast path to a running local environment. For day-to-day commands,
build gotchas, and deploy details, see
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Prerequisites

- **Node.js ≥ 20** and npm — for the dashboard (Next.js static export).
- **Python 3.11** (conda recommended) — for the prediction pipeline. _Only
  needed if you want to regenerate predictions; the dashboard runs against the
  JSON snapshot committed in the repo._

## Option A — just run the dashboard (≈2 minutes)

The repo ships a JSON snapshot under `website/public/data/`, so the site runs
with no Python and no API keys.

```bash
cd website
npm install        # honours .npmrc (legacy-peer-deps=true) — required
npm run dev        # → http://localhost:3000
```

## Option B — full prediction pipeline

```bash
# 1. Python environment
conda create -n f1_predictions python=3.11 -y
conda activate f1_predictions
pip install -r requirements.txt
pip install -r requirements-dev.txt     # pytest, ruff, mypy, etc.

# 2. (optional) configure secrets
cp .env.example .env                     # edit as needed; all keys are optional

# 3. Generate predictions + JSON for one round
python src/export_website_data.py --round 6 --fastf1 --advanced

# 4. Probability layer + evaluation
python src/export_probabilities.py --rounds 1,2,3,4,5,6
python src/forward_eval.py --season 2026 --allow-empty
```

> The pipeline degrades gracefully: external sources (FastF1, Jolpica) are
> rate-limited or may be offline; commands fall back rather than crash. See
> [`docs/ML_PIPELINE.md`](docs/ML_PIPELINE.md) for the full data flow.

## Verify your setup

```bash
# Python
pytest tests/ -q          # full suite (~390 tests, ~15s)
ruff check .              # lint

# Website
cd website
npm run lint
npm run build             # full static export (regenerates OG images + WebP)
```

If all four pass, you're ready to develop. Next stop:
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Environment variables

All optional for local dev. Full reference in
[`docs/ENV_VARS.md`](docs/ENV_VARS.md). The ones you're most likely to touch:

| Variable | Default | Purpose |
|---|---|---|
| `F1_SEASON_YEAR` | `2026` | Which season to publish |
| `F1_USE_LIVE_STANDINGS` | `1` | Pull official standings on export |
| `F1_REGISTRY_ENABLED` | `1` | Set `0` to no-op the model registry (handy for tests) |
| `NEXT_PUBLIC_SITE_URL` | GitHub Pages URL | Absolute URL for OG/sitemap (set to `http://localhost:3000` in dev) |

## Troubleshooting

- **`npm ci` fails on peer deps** — confirm `website/.npmrc` still contains
  `legacy-peer-deps=true`. Do not delete it (visx peers React 16–18; we run 19).
- **Modified `.webp` files after every build** — expected; `prebuild`
  regenerates WebP siblings non-deterministically. See
  [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md#build-gotchas).
- **FastF1 errors / rate limits** — FastF1 caps at ~500 req/hour. Backfills top
  out at ~24–30 rounds per run; re-run later.
