# RaceIQ F2 — readiness report

**Maturity: experimental** (runs end-to-end with a purpose-built model and a
real-feed-capable data layer; promotion to *production* is gated on validated
accuracy from a live feed). This report states exactly what works, what's reused,
and what remains before production.

## Capability checklist

| Capability | Status | Implementation | Reuses core? |
|---|---|---|---|
| Calendar ingestion | ✅ | `config.CALENDAR` → `F2DataSource.season()` | data.schema |
| Driver / team standings | ✅ | `pipeline.driver_standings` / `team_standings` | `core.standings` |
| Unique F2 model | ✅ | `model.estimate_skill` — Elo (rookie-pooled) + history + optional Bayesian | `core.elo`, `core.hierarchical_bayes` |
| Reverse-grid sprint | ✅ | `model.forecast_round` sprint head (top-10 reversed + grid penalty) | `core.calibration` |
| Merit feature race | ✅ | `model.forecast_round` feature head | `core.calibration` |
| Win/podium/top-6/top-10 + H2H | ✅ | Plackett-Luce Monte Carlo per race | `core.calibration` |
| Finishing-range intervals | ✅ | MC positional quantiles; confidence label | `core.conformal` |
| Championship simulation | ✅ | `model.project_championship_f2` (alternates sprint/feature points) | `core.championship` |
| Forward-eval / drift / promotion | ✅ | `forward_eval.py` / `drift_report.py` / `promotion_decision.py` | `core.eval` / `core.drift` / `core.promotion` |
| Website (home/race/standings/calendar/predictions/accuracy) | ✅ | `website/` static export | ecosystem design system |
| Per-round data contract | ✅ | `export.py` fan-out + TS+pydantic mirror gate | data.schema |
| Deployment | ✅ | `deploy-website.yml` ships F2 under `/<repo>/projects/f2` | — |
| Real results feed | ✅ | `FiaF2Source` scrapes fiaformula2.com (verified vs 2024); behind the source seam | data.sources |
| Probability calibration | ◑ | fits once ≥`MIN_REAL_ROUNDS_FOR_CALIBRATION` real rounds exist (honest gate) | `core.calibration` |
| Real season in the live pipeline | ◑ | regenerate `config` roster/calendar from `FiaF2Source.entry_list()`/`calendar()` | — |
| Validated accuracy → production | ⬜ | run `core.eval` over a real season once roster is repointed | `core.eval` |

## The unique F2 model

F2 is a **spec series** (identical machinery → driver skill dominates, team effect
minor) with **two structurally different races**: a merit-grid feature race and a
**reverse-grid sprint** (feature-quali top-10 reversed). The model
(`f2_predictions.model`) reflects this:

- **Latent skill blend** (leakage-safe, prior rounds only): `core.elo`
  (`EloFeatureBuilder` with rookie pooling for the series' high turnover) +
  smoothed finishing history + an optional `core.hierarchical_bayes` prior, with
  driver-dominant weights.
- **Feature head**: sample finishing orders from skill via Plackett-Luce.
- **Sprint head**: build the reversed grid, add a grid-position penalty so fast
  drivers starting at the back must overtake — producing the characteristic
  high-variance sprint (verified by tests: the sprint win is less concentrated
  than the feature win).
- **Championship**: a small F2-local Monte Carlo that alternates the sprint and
  feature points tables, reusing `calibration.sample_finishing_orders`.

The reverse-grid and race-type logic is the only genuinely new modelling code and
lives in the project; everything numerically heavy is shared core.

## Phase 2 — real data feed + calibration

Results are selected behind the `DataSource` seam (`f2_predictions.sources`):

- `SyntheticF2Source` — deterministic latent-pace fallback (default; CI-safe).
- `FastF1F2Source` / `OfficialF2Source` — real feeds, **probed at runtime**;
  return `None` (defer) on any failure since there is no stable public F2 results
  API today.
- `CompositeF2Source` — tries real feeds first, always falls back to synthetic,
  recording per-race **provenance**.

`F2DataSource` picks the composite when `F2_USE_LIVE_RESULTS=1`, else synthetic —
the public API is unchanged, so model/pipeline/export are agnostic to the source.
`backfill.py` writes predicted-vs-actual pairs into
`motorsport_data.store.HistoryStore` (sprint at a `+50` round sentinel). Probability
calibration (`export.build_calibrator`) fits a per-race-type
`StratifiedProbabilityCalibrator` **only from real rounds**, and the website
honestly reports `calibration.applied=false` until the gate trips — so running on
synthetic data never claims calibration it hasn't earned.

## Phase 3 — the real feed (built + verified)

`f2_predictions.sources.FiaF2Source` scrapes **fiaformula2.com**, the official
site, which serves each round's results as server-rendered HTML at
`/Results?raceid=N` — full Feature + Sprint classifications with a 3-letter driver
code and team per row, plus a season navigator that resolves every round's raceid
from a single anchor. It uses only the stdlib + a lazy `requests` import (no
lxml/bs4) and returns `None` on any failure, so it slots straight into the source
seam. The parser is unit-tested offline against a saved fixture; the live path is
the `f2_predictions.scrape` CLI:

```text
$ python -m f2_predictions.scrape --season 2024
 1 G. Bortoleto   Invicta Racing      211   ← real 2024 champion ✓
 2 I. Hadjar      Campos Racing       188
 3 P. Aron        Hitech Pulse-Eight  154
```

This produces the **real 2024 championship order** straight through
`motorsport_core.standings`, proving the feed works end-to-end. (Pole/fastest-lap
bonus points aren't on the race-classification table, so absolute totals differ
slightly from official — the order is the real result; bonuses are a later refinement.)

## Tests

50 F2 tests cover: calendar/roster, two-race weekends, deterministic results,
standings + the driver↔team points identity, **leakage** (skill uses prior rounds
only; Elo replay rejects future events), the **unique model** (sprint≠feature,
reverse-grid math, sprint variance, rookie pooling, range/championship scaling),
**sanity** invariants (full permutations, monotonic markets, complete exports),
the **TS+pydantic data contract**, the **source seam** (fallback + provenance),
the **calibration gate** (closed on synthetic, opens on real rounds), and the
**HistoryStore backfill** (both races, idempotent). Core/data: 92 tests unchanged.

## Path to production (remaining)

1. Wire a real `F2DataSource.results` — implement `FastF1F2Source._load` or
   `OfficialF2Source._fetch` once a stable F2 results source is available. Nothing
   downstream changes.
2. `F2_USE_LIVE_RESULTS=1 python -m f2_predictions.backfill` to persist real
   results; re-export so the calibration gate flips on honestly.
3. Validate accuracy with `forward_eval` / `drift_report` / `promotion_decision`
   over real rounds.
4. When accuracy clears thresholds, set `registry/projects/f2-predictions.json`
   `maturity` to `production` and relax the maturity assertion in `test_smoke.py`.
