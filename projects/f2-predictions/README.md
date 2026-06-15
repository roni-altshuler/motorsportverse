<div align="center">

<img src="../../website/public/brand/series/raceiq-f2.svg" alt="RaceIQ F2" width="320" />

# RaceIQ F2 — Formula 2 predictions

</div>

Qualifying, race, and championship forecasts for the **FIA Formula 2**
championship — the first fully operational expansion in the
[MotorsportVerse](../../README.md) ecosystem.

> **Maturity: experimental.** Full pipeline + website run end-to-end on the
> shared core. Results currently come from a reproducible latent-pace model
> pending a live F2 feed (see "Data" below) — accuracy is therefore not yet
> validated against real classifications.

## What it does

| Capability | How |
|---|---|
| Calendar ingestion | `config.CALENDAR` (shared F1 circuits) → `F2DataSource.season()` |
| Driver standings | `pipeline.driver_standings` → `motorsport_core.standings` |
| Team standings | `pipeline.team_standings` → `motorsport_core.standings` |
| Qualifying prediction | `pipeline.predict_round` (leakage-safe pace order) |
| Race prediction | `motorsport_core.calibration` Plackett-Luce probabilities |
| Championship simulation | `pipeline.project_title` → `motorsport_core.championship` |
| Monte Carlo forecasting | `championship.project_championship` (5k full-season sims) |
| Website | `website/` — home, standings, calendar, predictions |

## Reuse

The F2 product is **mostly shared infrastructure**:

- **Python pipeline: ~74% reused** — 389 LOC of F2-specific glue over ~1,128 LOC
  of `motorsport-core` + `motorsport-data` (calibration, championship, standings,
  eval, leakage, interfaces, schema).
- **Website: ~77% reused** — the MotorsportVerse design system, only pages + data
  layer are F2-specific.

The only genuinely F2-specific logic: points tables, the two-race weekend shape,
the roster/calendar, and the leakage-safe pace estimator. See
[docs/F2_READINESS.md](../../docs/F2_READINESS.md).

## Layout

```
src/f2_predictions/
  config.py       calendar, roster, teams, points systems, latent pace
  datasource.py   F2DataSource (motorsport_data DataSource)
  pipeline.py     standings + pace + quali/race prediction + championship (core glue)
  predict.py      F2Predictor (motorsport_core Predictor)
  export.py       writes website/public/data/f2.json
tests/            test_smoke.py + test_pipeline.py (18 tests)
website/          Next.js static export (RaceIQ F2)
```

## Run

```bash
pip install -e packages/motorsport-core packages/motorsport-data
pip install -e projects/f2-predictions --no-deps
pytest projects/f2-predictions
python -m f2_predictions.export
cd projects/f2-predictions/website && npm install && npm run build
```

## What's left for production

- Wire a **live results feed** (FastF1 F2 / official timing) in `datasource.results`.
- Validate forecast accuracy with `motorsport_core.eval` against real results,
  then promote maturity to `production`.
