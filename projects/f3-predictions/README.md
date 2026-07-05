<div align="center">

<img src="../../website/public/brand/series/raceiq-f3.svg" alt="RaceIQ F3" width="320" />

# RaceIQ F3 — Formula 3 predictions

</div>

Qualifying, sprint, feature-race, and championship forecasts for the
**FIA Formula 3** championship — the third series on the
[MotorsportVerse](../../README.md) core, built at RaceIQ F2 parity.

> **Maturity: experimental.** Full pipeline + website run end-to-end on the
> shared core against the **real 2026 season** (official results scraped into a
> committed snapshot). Forward accuracy is still accruing over live rounds, so
> the project stays `experimental` until enough real rounds validate it.

## What it does

| Capability | How |
|---|---|
| Real results ingestion | `sources/fia_f3_source.py` → shared `motorsport_data.sources.fia_feeder` (fiaformula3.com) |
| Committed snapshot | `python -m f3_predictions.refresh` → `data/official_2026.json` (reviewable, offline-reproducible) |
| Driver/team standings | official totals from the snapshot; recomputed fallback via `motorsport_core.standings` |
| Skill estimation | Elo (rookie-pooled) + finishing history + optional GBR/XGB signal (`ml_skill.py`), leakage-safe |
| Race-type heads | merit feature race + **reverse-top-12 sprint** with grid penalty (`model.py`) |
| Probabilities | `motorsport_core.calibration` Plackett-Luce Monte Carlo (win/podium/top-6/top-10, ranges) |
| Championship simulation | `model.project_championship_f3` — sprint+feature-aware title Monte Carlo |
| Race weekend automation | `race_weekend.py` — post-quali grid conditioning, freshness gate, stranded-round sweep |
| Website | `website/` — Next.js static export (RaceIQ design system, F3 gold) |

## The 2026 season facts

30-car grid (10 teams × 3), 9 rounds (the Sakhir round was cancelled), sprint
points 10-9-8-7-6-5-4-3-2-1 (top 10), feature points 25-18-15-12-10-8-6-4-2-1,
pole +2, fastest lap +1, sprint grid = feature-quali top **12** reversed — all
verified against fiaformula3.com round pages and official standings breakdowns.

## Layout

```
src/f3_predictions/
  config.py       calendar, roster, teams, points systems, model knobs
  datasource.py   F3DataSource (motorsport_data DataSource; snapshot-first seam)
  sources/        fia_f3_source (live scrape) / snapshot / synthetic + composite
  model.py        skill blend + feature/sprint heads + championship MC
  ml_skill.py     optional gradient-boosted skill signal (GBR + XGBoost)
  pipeline.py     standings + pace + forecasts (core glue)
  predict.py      F3Predictor (motorsport_core Predictor)
  export.py       writes website/public/data/*.json (mirrors the F1 fan-out)
  refresh.py      scrape fiaformula3.com → data/official_2026.json
tests/            91 tests — parser fixtures, leakage, model, pipeline, schema
website/          Next.js static export (RaceIQ F3)
```

## Run

```bash
pip install -e packages/motorsport-core packages/motorsport-data
pip install -e projects/f3-predictions --no-deps
cd projects/f3-predictions && PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m f3_predictions.export
PYTHONPATH=src python -m f3_predictions.refresh     # network: pull new rounds
cd website && npm install && npm run build
```

## What's left for production

- Accrue forward-eval accuracy over enough real rounds (`forward_eval.py`),
  then flip the honest calibration gate and promote maturity to `production`.
- Backfill 2024–2025 seasons into the HistoryStore for richer calibration.
