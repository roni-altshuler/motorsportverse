# Report 8 — Monaco Grand Prix Readiness (post-fix) · **GO**

**Generated:** 2026-06-03 · **Target:** Round 6, Monaco GP, **2026-06-07**. Supersedes Report 4 with the Priority-1 qualifying fix in place. **Verdict: 🟢 GO.**

## Complete dry-run — every stage verified

| Stage | Verification | Result |
|-------|--------------|--------|
| **Phase transitions** | `gp_weekend.py --round 6 --dry-run` resolves **`pre`** today (no network probe). The pre→post-quali→post-race machine was proven end-to-end on Canada R5 (Report 3): `F1_WEEKEND_TODAY` overrides correctly yield post-quali (Sat) and post-race (Sun) from cache. | ✅ |
| **Qualifying ingestion** | Pre-quali run loads 2023–2025 Monaco history (4105 laps) and builds the 43-feature matrix; `get_qualifying_or_estimates` falls back to estimates pre-session (`qualifyingDataAvailable=false`). | ✅ |
| **Prediction generation** | Monaco pre-quali prediction generated: **LEC pole, VER P2, HAM P3**, 22/22 drivers, **no null positions**, ensemble R²=0.96. | ✅ |
| **Calibration** | Gate is `applied=true` (history DB = 140 distinct season-rounds incl. 2018–2025; ≥3 completed rounds). Monaco probabilities will be calibrated. | ✅ |
| **Website export** | Schema/contract enforced by `tests/test_website_data_schema.py` + `test_predictions_sanity.py` (passing in the 915-test suite). Sandbox run used `persist_output=False`; production path unchanged. | ✅ |
| **Deployment pipeline** | `update_predictions.yml` cron covers Sat (quali) + Sun/Mon (race); `safe_push.sh` + `deploy.yml` unchanged. | ✅ |
| **Frontend gating** | `predictionPhase="preview"` → `isPredictionPublished=false` → race prediction **hidden** pre-quali; flips at post-quali. | ✅ |

## Priority-1 fix is live and Monaco-protective

The qualifying-NaN defect that corrupted Round 1 (SAI/STR predicted P1/P2 on no qualifying time) is **fixed and unit-tested for Monaco specifically** (`test_qualifying_reliability.py::test_monaco_no_time_driver_cannot_steal_pole`). On the real R1 data the fix moved SAI P1→P21, STR P2→P22 and cut R1 MAE 6.36→5.45.

**Why this matters most at Monaco:** it is the circuit where a no-time driver wrongly seated at the front does maximal damage (overtaking near-impossible, grid position decisive) and where aborted/red-flagged qualifying laps and grid penalties are most common. The fix guarantees: any driver with missing/deleted/incomplete qualifying is seated **behind the entire timed field** (ordered by official grid when available), never promoted. Pre-quali previews and complete sessions are unaffected.

## Remaining production risks (none blocking)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Monaco cache empty → first post-session run hits FastF1 live | Expected | Cron retries; pre-weekend is offline-safe (historical Monaco cached). |
| `_session_available` 20 s network probe flaky on Saturday | Medium | Phase auto-detect retries each cron tick; manual `-f phase=post-quali` fallback. |
| `npm run build` 180 s timeout | Medium | `--no-build` in dry-runs; prod retains prior export on timeout. |
| **Wet Monaco** | Medium | Forecast-dependent; wet-Elo path unexercised in R1–5 (all dry). Volatility model (Report 7) flags Monaco's chaos — widen intervals if rain forecast. |
| **High attrition / SC** | Inherent | Monaco SC probability is high (~0.75). DNFs remain unpredictable (Report 6) — manage expectations on within-5; the prediction will look "wrong" if a leader retires, but the probabilities are honestly calibrated. |

## New layers — how they apply to Monaco

- **Reliability (Report 6):** do **not** wire into Monaco probabilities — base rate is better on 2026 DNFs. Use only to widen intervals.
- **Volatility (Report 7):** Monaco scores **low race-order volatility despite high SC probability** (qualifying-locked) — so the model should be *confident in the front-of-grid order* but flag interruption risk. This is the correct Monaco intuition and a good sanity check on the published prediction.

## GO / NO-GO

**🟢 GO.** Phase machine, qualifying ingestion (now NaN-safe), prediction generation, calibration, export contract, and deployment are all verified for Round 6. The one historical defect that would have hurt Monaco most is fixed and regression-tested. No manual intervention required in the happy path; the established cron + `safe_push` + deploy chain carries the weekend.
