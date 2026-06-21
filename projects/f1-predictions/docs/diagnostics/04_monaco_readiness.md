# Report 4 — Monaco Grand Prix Prediction Readiness

**Generated:** 2026-06-03 · **Target:** Round 6, Monaco Grand Prix, **2026-06-07** (4 days out). **Verdict: 🟢 GO** — the intended pre-quali → post-quali → post-race workflow will execute automatically. Risks below are operational, not blocking.

## Intended workflow → verified behaviour

| Intended step | Verified |
|---------------|----------|
| Before qualifying: no final race prediction shown | ✅ `_detect_phase(6)` today returns **`pre`** (race 06-07, today 06-03 < quali 06-06; no network probe). `predictionPhase="preview"` → frontend `isPredictionPublished=false` → renders "Race Preview" placeholder, **hides classification** (`RaceDetailPage.tsx:262-265`). |
| After qualifying: model consumes latest quali + history | ✅ On Sat 06-06 `_detect_phase` probes FastF1 `Q`; when present → **post-quali** → `export_round_data(6, use_lstm=True, use_telemetry=True)` ingests real quali. |
| Generates race outcome probabilities | ✅ Probability layer runs; **calibration gate is already `applied=true`** (≥3 completed rounds; history DB = 140 season-rounds). |
| Website data updated automatically | ✅ `gp_weekend.py` writes round/standings/tracker JSON, then `safe_push.sh` commits; `deploy.yml` publishes. |
| Frontend displays updated prediction | ✅ `isPredictionPublished` flips true at `post-quali`; classification + probabilities render. |

`gp_weekend.py --dry-run` (no args) today auto-targets **Round 6 Monaco, phase pre, pipeline `export_round_data(6, use_weather_api=True)`** — exactly correct. Monaco `postponed=false` in `season.json`, so automation is not gated off.

## Cron coverage

`update_predictions.yml` fires Thu/Fri/Sat/Sun/Mon/Tue (multiple times Fri–Sun). The Saturday runs (`0,6,12,18` UTC) cover Monaco qualifying; Sunday/Monday runs cover the race + results backfill. Phase is auto-detected each run, so no manual scheduling is needed.

## Failure points & mitigations

| Risk | Severity | Detail / mitigation |
|------|----------|---------------------|
| **Monaco cache empty** | Expected | `f1_cache/2026/…Monaco…/` dirs exist but are empty (12 KB) — sessions haven't happened. First post-quali/post-race run hits FastF1 **live**. Mitigated by cron retries; pre-weekend uses cached historical Monaco years (offline-safe). |
| **FastF1 availability / 500 req-hr limit** | Medium | Saturday `_session_available` is a live 20 s-timeout network probe; the post-quali load pulls fresh data. A flaky/slow FastF1 endpoint delays (not breaks) — next cron retries. |
| **npm build (180 s timeout)** | Medium | Heaviest step. Needs `node_modules` present and `legacy-peer-deps`. On timeout the previous static export is retained; re-runs on next cron. |
| **Quali NaN handling** | Medium (Monaco-specific) | **Monaco is the highest-risk circuit for the R1-style bug** (Report 1): tight quali, frequent grid penalties, red-flag sessions → drivers with no representative time. If a front-runner has NaN quali, the model may seat them optimistically. Watch the post-quali output; see Report 5 Fix #2. |
| **Wet weather** | Low-Medium | Monaco can rain. Wet-weather Elo exists but was never exercised in R1–R5 (all dry). Unproven in production; a wet Monaco is an out-of-distribution test. |
| **DNF blindness** | Inherent | Monaco is a high-incident, low-overtaking street circuit — a safety-car/retirement is likely and will produce large misses the model cannot foresee. This is expected, not a defect; manage expectations on within-5 for this round. |

## Manual steps that could be needed

- **None in the happy path.** The pipeline is fully automated.
- Contingency only: if a cron run fails mid-weekend, `gh workflow run update_predictions.yml -f round=6 -f phase=post-quali` re-runs a single phase. If quali data is genuinely delayed upstream, the post-quali phase no-ops and retries — no intervention required.

## Conclusion

Monaco is **ready**. Phase detection, gating, calibration, and the export/deploy chain are all verified correct for round 6. The only Monaco-specific *model* risk is the qualifying-NaN edge case (elevated at this circuit) — recommend monitoring the first post-quali export and prioritising Fix #2 from Report 5 before a wet/disrupted qualifying session.
