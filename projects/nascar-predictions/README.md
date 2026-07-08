# NASCAR Cup Predictions

Oval and road-course forecasts for the NASCAR Cup Series — the fifth series on
the MotorsportVerse core, built to Formula E parity plus the NASCAR-specific
playoff machinery.

## What makes the Cup model different

- **Field-relative + per-track-type Elo.** NASCAR has no teammates in the F1
  sense, so every driver is rated against the whole field, with four extra
  Elo stacks (superspeedway / intermediate / short / road — near-different
  sports) blended in for the round's track type. Racing team and manufacturer
  (Chevrolet / Ford / Toyota) ride along as team-like effects.
- **DNF/crash head is first-class.** Cup attrition is 3-4x F1's and a
  superspeedway Big One can collect a third of the field. The race Monte
  Carlo *composes* a per-driver hazard (rolling `finishing_status` history +
  track-type attrition, shrunk) with the pace model: sample DNFs first, rank
  survivors by Plackett-Luce pace, retirees to the back.
- **Title odds run through the real championship format.** The 2026 Cup
  season is a Chase: 26-race regular season, top-16 on points, staggered
  seeding reset (2100/2075/2065…), a 10-race Chase with no eliminations, race
  win worth 55 points. `championship_playoffs.py` is a config-driven Monte
  Carlo engine that expresses both this format and the 2014-2025 elimination
  playoffs (used for backtests), sampling stages for stage points on the same
  shared Plackett-Luce sampler.
- **The playoff panel is gated by a backtest.** `playoff_backtest.py` replays
  2018-2025 through the elimination-format simulator at three checkpoints
  (mid-season / pre-playoffs / Round of 8) and reports whether the actual
  champions were assigned reasonable probability. The gate (champion mean
  percentile + probability-vs-uniform at pre-playoffs) lands in
  `historical_backtest/playoffs.json` — the website shows the playoff panel
  only on `gate.pass`.

## Data

Official cf.nascar.com cacher feeds (no auth): season race lists
(`race_list_basic.json`, `race_type_id == 1` filters exhibitions) and per-race
weekend feeds (full classification, per-stage top-10 with stage points,
qualifying runs, pre-race entry lists). Standings are derived by summing the
feed's `points_earned` (stage points included) because the cacher's standings
endpoints are gated. The archive floor is **2018** (the cacher answers `/2017/`
with the 2018 list; a `race_season` guard refuses it); stage results and
playoff-point rows start in the **2020** feeds.

Committed snapshots: `data/official_2026.json` (active season, written by
`refresh.py`) and `data/seasons/2018..2025.json` (written by
`backfill.py --history`). Every downstream build reads them offline. Raw API
responses cache under `data/api_cache/` (gitignored); the history store is
`data/history.duckdb` (gitignored, regenerable).

Wrong-event guards run on every live path (race_id + date + track cross-checks
against the human-verified config calendar, with bounded date tolerance for
rain delays), and a refresh can never regress the committed snapshot.

## Commands

```bash
# from projects/nascar-predictions, with the repo venv and OMP_NUM_THREADS=1
PYTHONPATH=src python -m nascar_predictions.refresh              # live snapshot pull
PYTHONPATH=src python -m nascar_predictions.backfill --history   # 2018→ archive pull
PYTHONPATH=src python -m nascar_predictions.backfill             # offline pred-vs-actual pairs
PYTHONPATH=src python -m nascar_predictions.export               # website JSON contract
PYTHONPATH=src python -m nascar_predictions.forward_eval --season 2026 --position-model-ab
PYTHONPATH=src python -m nascar_predictions.historical_backtest  # 2022→ replay
PYTHONPATH=src python -m nascar_predictions.playoff_backtest     # champion-probability gate
PYTHONPATH=src python -m nascar_predictions.drift_report --season 2026
PYTHONPATH=src python -m nascar_predictions.promotion_decision --season 2026
PYTHONPATH=src python -m nascar_predictions.race_weekend --detect-round
PYTHONPATH=src python -m nascar_predictions.season_rollover --auto
PYTHONPATH=src pytest -q                                         # fully offline
```

A/B levers (default OFF, promotion is verdict-driven):
`NASCAR_USE_POSITION_HEAD` (direct finishing-position head — current verdict:
production-better). `NASCAR_USE_LIVE_RESULTS=1` puts the live feed first in
the source stack (refresh/cron only; builds read snapshots).

## Website contract

`export.py` writes `website/public/data/`: `nascar.json`,
`rounds/round_NN.json`, `probabilities/round_NN.json` (track-type calibration
strata), `playoff_projection.json` (per-driver `p_make_playoffs`/`p_title`
ladder), `calibration_summary.json`, `seasons.json`; siblings write
`forward_eval/`, `historical_backtest/` (incl. `playoffs.json`),
`reliability_plots/`, `model_health.json`, `promotion_status.json`. The
pydantic mirror in `tests/test_website_data_schema.py` gates the contract.
