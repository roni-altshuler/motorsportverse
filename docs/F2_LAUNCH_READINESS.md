# RaceIQ F2 — Launch-Readiness Assessment

**Date:** 2026-06-17 · **Branch:** `feat/f2-production` · **Base:** `main` @ `de5cc5e`
**Scope:** Final report for the engagement that took RaceIQ F2 from a synthetic scaffold to a real-data product. Companion docs: [PROJECT_STATE_AUDIT](PROJECT_STATE_AUDIT.md) · [F2_DATA_AUDIT](F2_DATA_AUDIT.md) · [F2_DESIGN_REVIEW](F2_DESIGN_REVIEW.md) · [BRANDING_RECOMMENDATION](BRANDING_RECOMMENDATION.md).

---

## What changed

RaceIQ F2 was shipping an **invented 12-round calendar with synthetic results presented as the 2026 season**. It now runs on the **real 2026 FIA Formula 2 season**:

- **Calendar:** the official **14 rounds** in the correct order (incl. Miami R2 and Montréal R3, previously missing), with weekend dates.
- **Results:** **real classifications** for the 5 completed rounds, scraped from fiaformula2.com into a committed, offline, reviewable snapshot (`data/official_2026.json`).
- **Standings:** **exact** official driver & team totals (incl. pole / fastest-lap bonuses) — Minì 86, Tsolov 80, Câmara 69, … / Campos 134, Rodin 115, … — with coherent per-round points history.
- **Forecasts:** model predictions for upcoming rounds + a Monte-Carlo championship projection off the real current points.
- **Honesty:** the calibration gate now **opens legitimately** on 5 real rounds; `seasonAccuracy` is real model-vs-official accuracy; `dataSource` tags carry real provenance.

Root causes were traced and fixed (not patched blindly): the working FIA scraper was never wired into the live path; the calendar + completed-count were hardcoded; raceids are out of calendar order (the cause of the wrong schedule); `dataSource` was hardcoded `"synthetic"`. See [F2_DATA_AUDIT](F2_DATA_AUDIT.md) for the per-discrepancy trace.

## Deliverables

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | `docs/PROJECT_STATE_AUDIT.md` | ✅ |
| 2 | `docs/F2_DATA_AUDIT.md` (10 discrepancies → code paths) | ✅ |
| 3 | Real-2026 repoint (data layer + export + tests) | ✅ committed |
| 4 | `docs/F2_DESIGN_REVIEW.md` (+ Montréal aerial, screenshots) | ✅ |
| 5 | `docs/BRANDING_RECOMMENDATION.md` (+ adopt owner's brand board) | ✅ |
| 6 | Tests: 169 pass (was 160), ruff clean, both sites build | ✅ |
| 7 | This report + PR | ✅ |

## Verification (reproducible)

```bash
# refresh the real snapshot from fiaformula2.com (the only networked step)
PYTHONPATH=src python -m f2_predictions.refresh
# regenerate the site data + continuous-learning artifacts
PYTHONPATH=src python -m f2_predictions.export
PYTHONPATH=src python -m f2_predictions.forward_eval --season 2026 --allow-empty
# tests + lint + builds
PYTHONPATH=…/core/src:…/data/src python -m pytest packages projects/f2-predictions   # 169 pass
ruff check packages projects scripts                                                  # clean
cd projects/f2-predictions/website && npm run build                                   # 22 pages, 14 race routes
```
Cross-checked the regenerated `f2.json` calendar/standings against fiaformula2.com — match.

---

## Scorecard

| Dimension | Score | Rationale |
|-----------|:-----:|-----------|
| **Data accuracy** | **9.5 / 10** | Calendar, completed-count, results, and standings match official sources exactly (snapshot reconciles to the published totals). −0.5: 2 of the newest venues lack aerial photos / circuit-map geometry (graceful fallback). |
| **UI consistency** | **9 / 10** | F1-flagship design system 1:1, themed F2 blue; all pages render real data; "this is RaceIQ / this is F2" both legible. −1: Miami/Madrid/Lusail art gaps + a shared NumberTicker no-JS nicety. |
| **Prediction readiness** | **7.5 / 10** | Honest calibration applied on 5 real rounds; real forward-eval/drift; championship MC off real points. −2.5: forecast accuracy is modest (winner hit-rate 0.2, mean position error ≈ 4.9) — inherent to a high-variance spec series this early in the season, and now *honestly reported* rather than hidden. |
| **Production readiness** | **9 / 10** | Real data, deployed, CI green, reproducible pipeline, honest gating, **scheduled refresh Action**, and the owner's brand board now sliced into per-series web assets and wired onto the F2 site. −1: the season-long forward-eval is still accruing (2026 is mid-season). |

**Overall: promoted to `production` maturity** — the first MotorsportVerse expansion running on a real series with honest, official-accurate data, F1-parity UX, an automated update pipeline, and a deployed site.

---

## Maturity: promotion to `production`

Per `GOVERNANCE.md`, `experimental → production` requires **all** of: forward-eval over **≥1 full season**, a **deployed website**, and a **scheduled update workflow**.

| Gate | Met? | Note |
|------|:----:|------|
| Deployed website | ✅ | `deploy-website.yml` ships the F2 site under `/<repo>/projects/f2/` |
| Scheduled update workflow | ✅ | `refresh-f2.yml` runs `refresh → export → eval → drift → promotion` weekly and commits the snapshot only when it changes (live scrape isolated; builds read the committed snapshot) |
| Forward-eval ≥ 1 season | ◑ | 2026 is mid-season (5/14 rounds); the season-long stream is accruing automatically via the scheduled workflow. A completed-season retrospective can be produced on demand from the scraper's 2024 anchor if a published full-season report is wanted. |

The flag was flipped at the owner's direction (registry `maturity: production` + the `test_smoke.py` assertion relaxed). The deployment and automation gates are fully met; the season-long eval completes as 2026 runs — reported honestly rather than back-claimed.

## Remaining follow-ups (none block production)

1. **Branding** — ✅ the owner's brand board (`brand/source/raceiq-combined-logos.png`) is now **sliced into per-series web assets** (`website/public/brand/series/raceiq-*.png` lockups + `sports/*.png` marks, alpha-keyed), and the **RaceIQ F2 lockup is wired onto the F2 site** (navbar + footer). Optional upgrade: vectorise the rasters to SVG and switch the wordmark font to Orbitron for crisp scaling. (See BRANDING_RECOMMENDATION.)
2. **New-venue art** — aerial photos + circuit-map geometry for Miami, Madrid (Madring), Lusail when available (currently graceful fallbacks; Montréal added).
3. **Full-season eval report** — publish a completed-season retrospective (2024 backfill or end-of-2026) to close the eval gate with a formal artifact.
4. **Scraper hardening** — already captures retirements; add a current-season fixture test for `_parse_session` and a car-number alignment check.

## Risk notes

- The live FIA scrape is isolated to `refresh.py`; builds/tests read the **committed snapshot**, so a flaky or restructured site can never ship wrong data — it just means the snapshot isn't refreshed until the scraper is fixed.
- Jolpica/Ergast does **not** cover F2 (404) — do not reintroduce it as an F2 source.
- The F1 flagship (separate repo) was not touched.
