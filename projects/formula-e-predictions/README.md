# RaceIQ FE — Formula E predictions

E-Prix and championship forecasts for the **ABB FIA Formula E World
Championship** — the fourth series on the [MotorsportVerse](../../README.md)
core, built at F3 parity from the golden template.

> **Maturity: in-development (backend complete).** The full Python pipeline
> runs end-to-end on the shared core against the **real 2025-26 season**
> (official results from the Pulselive API in a committed snapshot; 13 of 17
> rounds complete). The website ships separately; `export.py` already emits
> the family's full data contract.

## What it does

| Capability | How |
|---|---|
| Real results ingestion | `sources/pulselive_source.py` → `api.formula-e.pulselive.com/formula-e/v1` (no auth; honest UA, ~1 req/s, disk-cached raw responses) |
| Wrong-event guard | every fetched race is verified against the human-verified config calendar (date/city/season + pinned championship id) — a mismatch raises, never ingests |
| Committed snapshots | `python -m formula_e_predictions.refresh` → `data/official_2026.json`; `backfill --history` → `data/seasons/<year>.json` (2019-2025) + `data/history.duckdb` (2015→present, 3 455 result rows) |
| Driver/team standings | official totals from the API (pole/fastest-lap bonuses included); recomputed fallback via `motorsport_core.standings` |
| Skill estimation | Elo seeded from real prior seasons (Gen2+ era window, Gen1 hard-cut) + current-season history + optional GBR/XGB signal (`ml_skill.py`, Gen3 window only), leakage-safe |
| Race head | single race per round; post-quali forecasts condition on the real grid (track position matters on street circuits) |
| Probabilities | `motorsport_core.calibration` Plackett-Luce Monte Carlo; isotonic calibration **stratified street vs circuit** |
| Championship simulation | `model.project_championship_fe` — race-points MC + expected pole (+3) / fastest-lap (+1) bonus adjustment |
| Validation | `forward_eval.py` (walk-forward vs **last-race** and **grid-order** baselines), `historical_backtest.py` (multi-season 2023→2026 + reliability PNGs), position-head A/B (`FE_USE_POSITION_HEAD`, default OFF) |
| Race weekend automation | `race_weekend.py` — freshness gate, phase detection, stranded-round sweep (doubleheader-aware one-day windows) |
| Season lifecycle | `season_rollover.py` + `bootstrap_next_season.py` (seasons keyed by ENDING year: 2026 = "SEASON 2025-2026") |

## The 2025-26 season facts (verified live against the API, 2026-07)

20-car grid (10 teams × 2), **17 points races** — doubleheaders in Jeddah,
Berlin, Monaco, Shanghai, Tokyo and London are two consecutive rounds sharing a
venue. Points 25-18-15-12-10-8-6-4-2-1, **pole +3**, **fastest lap +1** (top
10). Test events ("Valencia Testing", rookie tests) live in a separate
`FE_TESTS` championship and are filtered by `seriesType`; round numbers are
derived from date-ordered points races, never the API's `sequence`.

## Layout

```
src/formula_e_predictions/
  config.py            calendar (17 rounds), roster, teams, points, eras, model knobs
  datasource.py        FEDataSource (season-aware roster; snapshot-first seam)
  sources/             pulselive_source (live API) / snapshot / synthetic + composite
  model.py             era-windowed Elo seed + skill blend + race head + title MC
  ml_skill.py          optional gradient-boosted skill signal (GBR + XGBoost)
  position_head.py     opt-in direct finishing-position head (A/B-gated)
  pipeline.py          standings + pace + forecasts (core glue)
  export.py            writes website/public/data/*.json (fe.json + fan-out)
  forward_eval.py      walk-forward scoring vs last-race + grid-order baselines
  historical_backtest.py  multi-season replay + reliability diagrams
  refresh.py           Pulselive → data/official_2026.json (guarded)
  backfill.py          full 2014-15→present archive → duckdb + season snapshots
  race_weekend.py      freshness gate / phase / stranded-round recovery
  season_rollover.py   archive + start seasons; bootstrap_next_season.py
data/
  official_2026.json   committed active-season snapshot (offline source of truth)
  seasons/<year>.json  committed 2019-2025 season snapshots (Elo/backtest window)
  api_cache/           raw API responses (gitignored; cheap backfill reruns)
tests/                 125 offline tests — fixtures, wrong-event guards, leakage,
                       model, calibration gate, rollover, schema contract
```

## Run

```bash
# from the monorepo root (uv venv; see the root CLAUDE.md)
cd projects/formula-e-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q          # offline, no network
PYTHONPATH=src ../../.venv/bin/python -m formula_e_predictions.export
PYTHONPATH=src ../../.venv/bin/python -m formula_e_predictions.forward_eval --position-model-ab
PYTHONPATH=src ../../.venv/bin/python -m formula_e_predictions.historical_backtest

# network (data refresh only):
PYTHONPATH=src ../../.venv/bin/python -m formula_e_predictions.refresh
PYTHONPATH=src ../../.venv/bin/python -m formula_e_predictions.backfill --history
```

Env flags: `FE_USE_LIVE_RESULTS=1` (live-first source stack),
`FE_USE_POSITION_HEAD=1` (opt-in A/B head), `FE_SEASON_YEAR` /
`FE_DATA_DIR` (rollover/test seams). Pin `OMP_NUM_THREADS=1` for xgboost runs.
