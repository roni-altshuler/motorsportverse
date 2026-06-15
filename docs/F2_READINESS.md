# RaceIQ F2 — readiness report

**Maturity: experimental** (runs end-to-end; accuracy not yet validated against
real results). This report states exactly what works, what's reused, and what
remains before production.

## Capability checklist

| Capability | Status | Implementation | Reuses core? |
|---|---|---|---|
| Calendar ingestion | ✅ | `config.CALENDAR` → `F2DataSource.season()` | data.schema |
| Driver standings | ✅ | `pipeline.driver_standings` | `core.standings` |
| Team standings | ✅ | `pipeline.team_standings` | `core.standings` |
| Qualifying prediction | ✅ | `pipeline.predict_round` (pace order) | `core.leakage` |
| Race prediction | ✅ | Plackett-Luce win/podium probabilities | `core.calibration` |
| Championship simulation | ✅ | `pipeline.project_title` | `core.championship` |
| Monte Carlo forecasting | ✅ | 5k full-season sims, P10/mean/P90 | `core.championship` |
| Website (home/standings/calendar/predictions) | ✅ | `website/` static export | ecosystem design system |
| Live results feed | ⬜ | `F2DataSource.results` (latent-pace model today) | — |
| Validated accuracy | ⬜ | needs real results + `core.eval` | `core.eval` |

## Reuse — measured

**Python pipeline: ~74% reused.**

| Layer | Effective LOC |
|---|---|
| F2-specific (`config`, `datasource`, `pipeline`, `predict`, `export`) | 389 |
| Shared `motorsport-core` used (`calibration`, `championship`, `standings`, `eval`, `leakage`, `interfaces`) | 1,032 |
| Shared `motorsport-data` used (`schema`, `sources/base`) | 96 |
| **Total effective** | **1,517 → 74% shared, 26% F2** |

**Website: ~77% reused** — 1,702 LOC of design system (`ui/`, `magicui/`,
`lib/motion`, `tokens.css`) vs 508 LOC of F2 pages/nav/data.

The only genuinely F2-specific logic: the **points tables** (sprint + feature +
pole/FL bonus), the **two-race weekend** shape, the **roster/calendar**, and the
**leakage-safe pace estimator**. Everything numerically heavy — sampling,
calibration, championship Monte Carlo, standings math — is shared core.

### New reusable infrastructure this added to the core

Building F2 surfaced two genuinely cross-series capabilities, so they were added
to `motorsport-core` (not F2) — every future series gets them free:

- `motorsport_core.standings` — `compute_driver_standings`, `compute_team_standings`,
  `merge_standings` (multi-race weekends: F2 sprint+feature, F1/MotoGP sprint).
- `motorsport_core.championship` — `project_championship` Monte Carlo, reusing
  `calibration.sample_finishing_orders` (no duplicated sampling).

## Correctness & leakage

- **Leakage-safe pace estimation**: `pipeline.estimate_pace` aggregates only
  rounds strictly before the target round and asserts it via
  `core.leakage.assert_prior_only`. The predictor never sees the latent
  `config._TRUTH_PACE` used to generate results.
- **Determinism**: all sampling is seeded; results, predictions, and championship
  projections are reproducible across runs (covered by tests).

## Tests

18 F2 tests (`test_smoke.py` + `test_pipeline.py`) cover calendar ingestion,
two-race weekends, deterministic results, driver/team standings, the
driver↔team points identity, leakage-safe pace, qualifying+race prediction
shapes and probability validity, the championship projection (sums to 1,
sorted, points monotonicity, seed determinism, races-per-round scaling), and
the export JSON contract. Plus 10 new core tests for `standings`/`championship`.

## Sample output (2026 season, 7/13 rounds)

```
Drivers:  P1 Antonelli (Prema) 147 pts · P2 Verschoor (Trident) 102 · P3 Martins (ART) 100
Title:    Antonelli 94.9% · Bortoleto 3.4% · Martins 0.9%
Next:     Round 8 Great Britain — predicted podium MAR / BOR / HAD
Teams:    Prema 187 · Trident 117 · DAMS 112
```

## Path to production

1. Implement `F2DataSource.results` against a live feed (FastF1 F2 support or the
   official F2 timing API). Nothing else in the pipeline changes — it already
   consumes the `motorsport_data` schema.
2. Backfill real results into a `motorsport_data.store.HistoryStore`.
3. Validate forecast accuracy with `motorsport_core.eval.score_round` over a
   season; publish a forward-eval report.
4. Promote the registry entry `maturity` to `production`.
