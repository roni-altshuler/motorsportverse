# 🏎️ F1 Race Predictions — 2026 Season (v3.1)

A **modular, scalable** machine-learning framework that predicts Formula 1 Grand Prix
race results using historical telemetry from the [FastF1](https://docs.fastf1.dev/) API,
an ensemble regression approach, and an interactive **Next.js website** for visualisation.

> **Current season:** Official 22-round 2026 calendar, updated through the Miami Grand Prix weekend.
>
> **Live data sync:** Official standings and completed-round classified results are pulled from Jolpica/Ergast-compatible APIs with local fallback and freshness metadata.

---

## 🚀 Project Overview

This project uses **Gradient Boosting** and **XGBoost** regressors trained on
multi-season historical race data to predict finishing orders for upcoming F1 races.
Inspired by
[mar-antaya/2025_f1_predictions](https://github.com/mar-antaya/2025_f1_predictions),
it has been adapted and extended for the **2026 regulation era** with 11 teams and
22 drivers (including the new Cadillac F1 team).

### Architecture (v3)

```
f1_predictions/
├── f1_prediction_utils.py           ← Core ML framework (model, data, viz, reports)
├── advanced_models.py               ← Pit strategy, tyre deg, LSTM, season tracker
├── export_website_data.py           ← Data pipeline: ML → JSON + PNG for website
├── benchmark_game_theory_upgrades.py← Baseline vs enhanced benchmarking on completed rounds
├── optimize_game_theory_postprocessing.py ← Scale search for postprocessing calibration
├── generate_fastf1_viz.py           ← FastF1 historical visualisations (track map, etc.)
├── report_results.py                ← Detailed race report + HTML generator
├── create_season_races.py           ← Script that generates configured-season race files
├── F1PredictionFramework.ipynb      ← Interactive Jupyter notebook
├── requirements.txt
├── .gitignore
├── README.md
│
├── races/                           ← round-specific prediction scripts
│   ├── round_01_australia_gp.py
│   ├── round_02_china_gp.py
│   ├── ... (configured calendar)
│   └── round_22_abu_dhabi_gp.py
│
├── website/                         ← Next.js interactive dashboard
│   ├── src/
│   │   ├── app/                     ← App routes (/, /race/[round], /standings, etc.)
│   │   ├── components/              ← React components (HomePage, RaceDetail, etc.)
│   │   ├── lib/                     ← Data fetching utilities
│   │   └── types/                   ← TypeScript interfaces
│   └── public/
│       ├── data/                    ← Generated JSON (season, standings, rounds/)
│       └── visualizations/          ← Generated PNGs (round_01/, round_02/, ...)
│
├── visualizations/                  ← Legacy per-GP plots (gitignored)
├── reports/                         ← Generated HTML race reports (gitignored)
└── f1_cache/                        ← FastF1 data cache (gitignored)
```

---

## ✨ What's New in v3.1

### Website Dashboard
- **Next.js 16** + React 19 + Tailwind CSS v4 + Recharts
- Sleek race-control aesthetic with team colours, responsive layout, and source/freshness chips
- Pages: Home, Calendar, Race Detail, Standings (Drivers / Constructors / WDC), Accuracy, About
- Race-detail visualizations display inline with analyst notes, featured charts, KPI tiles, category chips, and source labels

### Advanced Models (`advanced_models.py`)
- **Pit Strategy Simulator** — Monte-Carlo simulation of 1/2/3-stop strategies with compound modelling
- **Tyre Degradation Curves** — Circuit-scaled compound degradation rates with cliff modelling
- **LSTM Lap Predictor** — PyTorch sequence model (falls back to analytical if no GPU)
- **Season Tracker** — Compares predictions vs actuals with accuracy metrics

### Data Pipeline (`export_website_data.py`)
- Single command exports JSON + PNG for the entire website
- Flags: `--round N`, `--all`, `--fastf1`, `--advanced`, `--metadata`, `--disable-game-theory`, `--game-theory-sims`, `--game-theory-neighbors`
- Generates `season.json`, `standings.json`, `round_XX.json`, and all PNG visualisations
- `standings.json` now defaults to official Jolpica standings (`F1_USE_LIVE_STANDINGS=1`)
- Completed round files can now refresh `actualResults` directly from official classified race results (`F1_USE_LIVE_ROUND_RESULTS=1`)
- Round files include `weekendResults` session tabs for sprint qualifying, sprint race, Grand Prix qualifying, and race classification when upstream data is available
- `season.json`, `standings.json`, and round files include freshness/source fields for website transparency
- Round metadata validates stored files against the current calendar so stale generated artifacts do not masquerade as current rounds

### Calibration & Benchmarking
- `benchmark_game_theory_upgrades.py` compares baseline vs enhanced game-theory variants across completed rounds
- `optimize_game_theory_postprocessing.py` performs scale search and validation passes, writing JSON reports under `reports/`
- Default `F1_GAME_THEORY_POSTPROCESS_SCALE` is tuned to `1.2` (env override supported)

### FastF1 Visualisations (`generate_fastf1_viz.py`)
- Circuit track maps (coloured by speed)
- Historical lap-time distributions
- Tyre strategy waterfall charts

---

## 📊 v2.0 → v3.0 Model Improvements

| Feature | v1 | v2 | v3 |
|---------|----|----|-----|
| Feature scaling | None | StandardScaler | StandardScaler |
| Team changes | Not handled | Team-change adjust | Team-change adjust |
| Pit strategy | None | Expected stops × loss | **Monte-Carlo simulation** |
| Tyre degradation | None | Circuit wear factor | **Compound-specific curves + cliff** |
| Driver experience | None | Log-scaled starts | Log-scaled starts |
| Prediction spread | 19.1s ❌ | ~1.7s ✅ | ~1.7s ✅ (calibrated) |
| Season tracking | None | Current-form feature | **Prediction vs actual tracker** |
| Reports | Console only | HTML report | **Interactive website** |
| LSTM | None | None | **Lap-by-lap sequence model** |
| Visualisations | 5 per GP | 5 per GP | **10+ per GP** (ML + FastF1 + advanced) |
| Races covered | 1 | Static scripts | **Configured-season pipeline + website** |

---

## 🏁 2026 Grid

| Team | Driver 1 | Driver 2 |
|------|----------|----------|
| Red Bull Racing | Max Verstappen (VER) | Isack Hadjar (HAD) |
| McLaren | Lando Norris (NOR) | Oscar Piastri (PIA) |
| Ferrari | Charles Leclerc (LEC) | Lewis Hamilton (HAM) |
| Mercedes | Kimi Antonelli (ANT) | George Russell (RUS) |
| Aston Martin | Fernando Alonso (ALO) | Lance Stroll (STR) |
| Alpine | Pierre Gasly (GAS) | Franco Colapinto (COL) |
| Williams | Alexander Albon (ALB) | Carlos Sainz (SAI) |
| Racing Bulls | Liam Lawson (LAW) | Arvid Lindblad (LIN) |
| Haas | Esteban Ocon (OCO) | Oliver Bearman (BEA) |
| Audi | Nico Hülkenberg (HUL) | Gabriel Bortoleto (BOR) |
| Cadillac | Sergio Pérez (PER) | Valtteri Bottas (BOT) |

---

## 📦 Dependencies

### Python (ML pipeline)

| Package | Purpose |
|---------|---------|
| `fastf1` | Historical F1 data retrieval |
| `pandas` / `numpy` | Data manipulation & numerical computing |
| `scikit-learn` | Gradient Boosting, StandardScaler, metrics |
| `xgboost` | XGBoost regression model |
| `matplotlib` / `seaborn` | Plotting & visualisations |
| `tqdm` | Progress bars |
| `torch` *(optional)* | LSTM model (falls back to analytical) |

### Website

| Package | Purpose |
|---------|---------|
| `next` 16.x | React framework + SSR/SSG |
| `react` 19.x | UI components |
| `tailwindcss` v4 | Utility-first CSS |
| `recharts` | Interactive charts |
| `framer-motion` | Animations |
| `@heroicons/react` | Icons |

---

## ⚙️ Environment Setup

```bash
# 1. Create conda environment
conda create -n f1_predictions python=3.11 -y
conda activate f1_predictions

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install website dependencies
cd website && npm install && cd ..

# 4. (Optional) Register Jupyter kernel
pip install ipykernel
python -m ipykernel install --user --name f1_predictions --display-name "Python (F1 Predictions)"
```

---

## ▶️ How to Run

### Full pipeline (ML → Website data)

```bash
conda activate f1_predictions

# Export Round 1 with all visualisations + advanced models
python export_website_data.py --round 1 --fastf1 --advanced

# Export the configured official calendar
python export_website_data.py --all --fastf1 --advanced

# Metadata only (season.json + standings.json)
python export_website_data.py --metadata

# Round export with game-theory overrides
python export_website_data.py --round 3 --game-theory-sims 900 --game-theory-neighbors 3
```

### Benchmark & tune game-theory enhancements

```bash
# Compare baseline vs enhanced behavior on completed rounds
python benchmark_game_theory_upgrades.py --rounds 1 2 3 --field-sims 700 --neighbors 2

# Sweep postprocessing scales and save tuning report
python optimize_game_theory_postprocessing.py --rounds 1 2 3 \
  --scales 0.6,0.8,1.0,1.2,1.4 --search-field-sims 180 --validate-field-sims 700
```

### Runtime environment toggles

```bash
# Season selection (defaults to DEFAULT_SEASON_YEAR; CI falls back to `date +%Y`)
export F1_SEASON_YEAR=2026

# Official data source toggles
export F1_USE_LIVE_STANDINGS=1
export F1_USE_LIVE_ROUND_RESULTS=1

# Game-theory feature and postprocess controls
export ENABLE_GAME_THEORY_ENHANCEMENTS=1
export F1_GAME_THEORY_POSTPROCESS_SCALE=1.2
export F1_GAME_THEORY_UNCERTAINTY_SCALE=1.2

# Live betting / value-finder integration (free key at https://the-odds-api.com/)
# Used by odds_ingest.py and export_value_data.py. Note: The Odds API does not
# currently include Formula 1 in its catalog (verified 2026-05) — the key works
# but no live F1 outrights data is available there at the moment. See
# docs/ENV_VARS.md for the full reference and the alternative-source roadmap.
export ODDS_API_KEY=...
```

Full reference for every variable the project reads: **[`docs/ENV_VARS.md`](docs/ENV_VARS.md)**.

### Local development setup

The project uses a `.env` file at the project root for local credentials.
`python-dotenv` is included in `requirements-dev.txt` (optional); when it is
not installed the code falls back to plain `os.environ`, so production / CI
runs that inject env vars directly continue to work unchanged.

```bash
# 1. Copy the template and fill in your real key(s).
cp .env.example .env
# 2. Edit .env — at minimum, set ODDS_API_KEY if you want the /value page.
# 3. (Optional) install dev deps so dotenv loads .env automatically.
pip install -r requirements-dev.txt
```

`.env` is gitignored — never commit your real key.

### Live `/value` page

The `/value` page surfaces positive-edge betting opportunities by comparing
the model's calibrated probabilities to current bookmaker odds. Data flow:

```
export_probabilities.py  ──►  website/public/data/probabilities/round_NN.json
                                                                            \
                                                                             ─►  export_value_data.py  ──►  website/public/data/value/round_NN.json  ──►  /value page
                                                                            /
odds_ingest.py           ──►  odds_cache/round_NN_<timestamp>.json
```

1. `export_probabilities.py` runs the Plackett–Luce Monte Carlo over predicted
   lap times and writes per-round market probabilities (`win`, `podium`,
   `top6`, `top10`, plus an H2H matrix). Calibration is honestly gated to
   `applied=false` until 3+ completed historical races are available.
2. **Odds source** — write a timestamped cache file under `odds_cache/`. The
   Odds API does *not* cover F1 (verified 2026-05); two free working paths,
   plus a unified wrapper that does both at once:

   **Unified (recommended): one command, auto-selects + merges available sources:**
   ```bash
   # Auto: uses Betfair if BETFAIR_* env vars set, CSV if odds_inbox/round_NN.csv
   # exists, best-back merge if both are available.
   python odds_ingest_unified.py --round 6 --season 2026

   # Force a strategy:
   python odds_ingest_unified.py --round 6 --season 2026 --merge best-back
   python odds_ingest_unified.py --round 6 --season 2026 --merge average
   python odds_ingest_unified.py --round 6 --season 2026 --merge prefer-csv
   ```
   The unified ingester looks for a CSV at `odds_inbox/round_NN.csv` by
   default; override with `--csv path/to.csv`. Both sources can be used
   together — `best-back` takes the higher decimal odds per driver
   (best price for the bettor), `average` averages implied probabilities.

   **Multi-bookmaker scraper + bulk CSV ingester (`odds_scraper.py`):**
   ```bash
   # Drop CSVs named round_NN_<bookmaker>.csv into odds_inbox/, then:
   python odds_scraper.py --round 6 --season 2026 --ingest-only

   # Scrape Oddschecker (best-effort; HTML scraping can break) + ingest:
   python odds_scraper.py --round 6 --season 2026 --scrape oddschecker

   # All registered scrapers + every inbox CSV → one multi-bookmaker snapshot:
   python odds_scraper.py --round 6 --season 2026 --scrape all
   ```
   The scraper writes one snapshot listing **every** bookmaker found, and
   `select_bookmaker` in `export_value_data.py` automatically picks the
   sharpest available book (Pinnacle > Betfair > … > lowest overround).
   Filename → bookmaker key: `round_06_pinnacle.csv` → `pinnacle`,
   `round_06_betfair_ex_eu.csv` → `betfair_ex_eu`, plain `round_06.csv` →
   `oddschecker_manual`. Web scraping is best-effort with `robots.txt`
   checks, a polite User-Agent, and 1-second pacing between sources; if
   any source fails (403, schema change, etc.) the scraper logs and falls
   back to whatever CSVs are already in the inbox.

   **a) Manual CSV from Oddschecker (fastest, no credentials):**
   ```bash
   # 1. Print a template with all 22 drivers, save to odds_inbox/:
   mkdir -p odds_inbox
   python odds_import_csv.py --print-template > odds_inbox/round_06.csv
   # 2. Open https://www.oddschecker.com/motorsport/formula-1/monaco-grand-prix/winner
   # 3. Paste the odds into the second column of the CSV.
   # 4. Run odds_ingest_unified.py (above) — it auto-discovers the inbox file.
   #    Or import directly via the single-source ingester:
   python odds_import_csv.py --round 6 --season 2026 \
       --bookmaker oddschecker_manual --csv odds_inbox/round_06.csv
   ```
   Driver names can be 3-letter codes (`VER`), last names (`Verstappen`), or
   full names. Fractional odds (`5/2`) and decimal (`3.50`) both accepted.

   **b) Betfair Exchange API (one-time setup, then unattended):**
   ```bash
   pip install betfairlightweight        # not in requirements-dev.txt by default
   # Add BETFAIR_USERNAME, BETFAIR_PASSWORD, BETFAIR_APP_KEY to .env
   python odds_ingest_betfair.py --round 6 --season 2026
   ```
   Requires a KYC'd Betfair account (UK/IE/AU/GR/ES/IT/DE) and a free dev
   app key from https://developer.betfair.com/.

3. `export_value_data.py` joins the two, de-vigs the bookmaker prices,
   computes per-driver `edgePct = (modelP − marketP) / marketP`, applies
   fractional-Kelly sizing (default 0.25× with a 5% per-bet cap and 30%
   portfolio cap), and writes the JSON consumed by the page.
4. The page renders a sortable edge table with a 360px-viewport card view,
   and surfaces the calibration disclaimer when `calibration.applied=false`.

See [`MODEL_CARD.md`](MODEL_CARD.md) for the ethical-use framing,
fractional-Kelly choice rationale, and known limitations of this pipeline.

### Start the website

```bash
cd website
npm run dev          # → http://localhost:3000
npm run build        # Production build
```

### Run a standalone GP prediction

```bash
python races/round_01_australia_gp.py
python races/round_06_monaco_gp.py
```

### Generate FastF1 visualisations separately

```bash
python generate_fastf1_viz.py --circuit Australia --year 2024 --round 1
```

### Generate HTML race report

```bash
python report_results.py
# → reports/Australian_Grand_Prix/race_report.html
```

### After qualifying (Saturday)

1. **Re-run the export** — `get_qualifying_or_estimates()` auto-fetches real qualifying times.
2. Update rain probability and temperature with the latest forecast.

### Season progression

After each real race weekend:
```bash
# 1. Run the export for the completed round
python export_website_data.py --round N --fastf1 --advanced

# 2. The season tracker auto-compares predictions vs actual results
# 3. Later rounds automatically use CurrentForm from earlier results
```

### Automated Updates (GitHub Actions)

The **Update Race Predictions** workflow (`.github/workflows/update_predictions.yml`) automates the full pipeline:

**Scheduled (automatic):** Runs repeatedly from **Thursday through Monday UTC** during race weekends. The workflow now always uses the Python auto-detection path, so it can publish preview predictions before the Grand Prix starts, refresh them once qualifying data is available, and keep retrying after the race until official results land in FastF1.

**Manual:** Go to **Actions → Update Race Predictions → Run workflow**, enter a round number (or `next` / `all`), and select options.

The workflow:
1. Runs the ML pipeline (`export_website_data.py`)
2. Generates visualizations (PNGs) into `website/public/`
3. Imports any locally generated visualizations from `visualizations/{GP_Name}/`
4. Commits data + viz files back to `main`
5. Calls the Pages deployment workflow so GitHub Pages updates even when the commit was created by `GITHUB_TOKEN`

```
Race Weekend Flow:
  Thursday/Friday  → Preview forecast publishes before the GP starts
  Saturday         → Auto-detects qualifying availability and refreshes race predictions
  Sunday           → Keeps polling until official results are available
  Monday           → Final backfill window for delayed FastF1 classification data
```

### Sprint Race Weekends

6 rounds in 2026 are **sprint weekends** (China, Miami, Austria, Belgium, USA, Brazil). The calendar data includes `sprint: true` and `sprint_laps` for these rounds. Sprint weekends have a modified schedule with Sprint Qualifying on Friday and the Sprint Race on Saturday before main qualifying.

### Circuit-Specific Features

The ML model incorporates detailed circuit characteristics that vary per track:

| Feature | Description |
|---------|-------------|
| **Expected pit stops** | 1-stop (Monaco, Monza, Zandvoort) vs 2-stop (most circuits) |
| **Tyre degradation** | Circuit-scaled wear factor (0.30 Monaco → 0.70 Qatar/Barcelona) |
| **Overtaking difficulty** | Track-specific overtaking rating (0.1 Monaco → 0.8 Monza) |
| **DRS zones** | Number of DRS activation zones (1–3 per circuit) |
| **Safety car likelihood** | Historical probability of safety car deployment |
| **Altitude** | Track elevation in metres (affects engine performance — e.g. Mexico at 2240m) |
| **Pit time loss** | Circuit-specific pit lane transit time (21.5s–23.5s) |

---

## 📈 Model Performance

The ensemble is evaluated on a held-out 20% test split:

| Metric | Round 1 (Australia) |
|--------|---------------------|
| **R²** (Ensemble) | 0.927 |
| **MAE** (Ensemble) | 0.147s |
| **Max Spread** | 1.73s |
| **Training Data** | 2023–2025 (2,699 laps) |

---

## 🖼️ Visualisations Per Round

Each round generates up to **10+ visualisations**:

| Category | Plots |
|----------|-------|
| **ML Predictions** | Predicted lap times, feature importance, team vs pace, pace vs predicted, lap-time distribution |
| **Advanced Models** | Pit strategy comparison, tyre degradation curves |
| **FastF1 Historical** | Track map (speed-coloured), historical lap-time distributions, tyre strategy waterfall |

The website now presents these as a visual lab: one large selected chart, a quick-switch rail, and compact category galleries so users can compare views without opening image modals.

---

## 📌 Roadmap

The full audit-driven ladder lives in the project plan; below is the
condensed public-facing version. See [`MODEL_CARD.md`](MODEL_CARD.md) for the
honest disclosure of which Tier-1 items are gated on additional data.

**Tier 0 — foundation (done)**

- [x] Leakage guards (`leakage.py`) + machine-checked assertions in feature build
- [x] Full pytest suite (118+ tests) with schema + golden-file checks in CI
- [x] Pinned requirements; archived `_v1.py` legacy
- [x] Live qualifying / weather / standings sync; Jolpica + FastF1 fallback
- [x] Sprint race + circuit-specific features (DRS, safety car, altitude, pit)
- [x] Game-theory postprocess benchmark + tuning harness

**Tier 1 — betting tool**

- [x] Calibrated probability layer (Plackett–Luce + isotonic, honest `applied=false` gate)
- [x] Fractional-Kelly sizing + DuckDB-backed backtest scaffold
- [x] `/value` page with sortable edge table and 360px-viewport card view
- [x] OddsAPI client + cache + de-vig (`odds_ingest.py`, `export_value_data.py`)
- [ ] Live odds source — **blocked**: The Odds API has no F1 coverage (2026-05). Alternatives tracked in [`docs/ENV_VARS.md`](docs/ENV_VARS.md): Pinnacle direct, Betfair Exchange, manual CSV.
- [ ] Multi-season historical backfill (2023+2024+2025) — flips `calibration.applied` to `true`

**Tier 2+ — modeling depth, UX polish, long-term ambition**

- [ ] Optuna hyperparameter search with time-series CV
- [ ] Conformal prediction intervals (MAPIE)
- [ ] Per-race OG images, sitemap, structured data
- [ ] Multi-season accuracy tracking dashboard

---

🏎️ **Predict every race of the 2026 season!** 🚀
