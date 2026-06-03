# Report 5 — Prioritized Improvement Roadmap

**Generated:** 2026-06-03 · **Basis:** Reports 1–4 only. Every item is evidence-linked; no speculative changes.

## Where the error actually comes from (evidence-ranked)

From the audit: **24 of 110 finishing slots (22%) across R1–R5 were DNF/DNS/Retired**, and accuracy tracks attrition inversely (Japan, 2 DNFs → MAE 2.0 and 22/22; Canada/Australia, 5–6 DNFs → MAE 5.4–6.4). The pace core is sound (Report 1, R3). The current-vs-original comparison (Report 2) shows model tuning has **not** moved completed-race accuracy (MAE 4.51 = 4.51) because none of it addresses the actual error sources below.

| Rank | Error source | Category | Evidence | Est. impact | Tractability |
|------|-------------|----------|----------|-------------|--------------|
| **1** | **No DNF / reliability model** | Model limitation | 24 DNFs; every worst miss (R2 NOR/PIA, R4 HAD/GAS/LAW, R5 RUS/NOR) is a retirement of a highly-rated car | **Highest** — dominates MAE on 4 of 5 rounds | Medium |
| **2** | **Qualifying-NaN handling** | Data quality | R1 SAI/STR predicted P1/P2 with NaN quali, started P21/P22 (−14/−15) | High *when it occurs*; rare but catastrophic; **elevated at Monaco** | **Easy** |
| **3** | **Within-race-randomness ceiling** | Race randomness | Even clean races scatter; DNFs of front cars (R5) are genuinely unpredictable | Caps achievable accuracy; affects honesty of probabilities | N/A (manage via calibration) |
| **4** | **Prior-round form fell back to predicted** | Data quality | `season_results_2026.json` lacked R1–R3 actuals → form features used predicted positions | Low-Medium (subtle feature degradation) | **Fixed in this work** |
| **5** | **Wet-weather path unproven** | Missing-feature risk | All R1–R5 dry; wet Elo never engaged | Latent (wet Monaco/Spa) | Medium |

## Recommended actions, in priority order

### 1. Add a DNF / finish-probability model *(highest impact)*
**Why:** the single largest, repeatable error source. **What the evidence supports:** a per-driver/per-circuit retirement probability that feeds the race-outcome layer, so a highly-rated car that retires has its *expected* finish pulled down and, more importantly, the **podium/win probabilities reflect reliability risk** instead of overclaiming. A `models/dnf.py` and `test_dnf_model.py` already exist in the tree — assess what's there and wire its output into the Plackett-Luce / race-simulator layer rather than building new. **Do not** try to predict *which* race a DNF happens (irreducible); do price the *rate*. Validate via Brier on podium/win across R1–R5, not position MAE (which DNFs will always punish).

### 2. Fix qualifying-NaN handling *(easiest high-value win, do before a wet/disrupted quali)*
**Why:** R1 proved a driver with no Q time gets an optimistic front-grid estimate. **What:** when a driver's qualifying `Position`/time is NaN, seat them from the **actual grid/classification fallback** (back of grid, or pit-lane start), not a pace estimate; or cap the estimate at the slot implied by the official grid. **Monaco-urgent** — this circuit produces NaN/aborted quali laps and grid penalties most often. Add a regression test from the R1 SAI/STR case.

### 3. Make the probability layer own the randomness *(honesty, not accuracy)*
**Why:** position MAE is bounded by attrition we can't predict (Report 1, R5). **What:** lean on calibration + the DNF rate (Fix #1) so the published *probabilities* stay well-calibrated even when point predictions miss. Surface wider finish ranges on high-incident circuits (Monaco, Singapore, Baku) via the existing `CircuitSafetyCar` feature. This converts "looks wrong" races into "honestly uncertain" ones.

### 4. Keep the actuals files complete *(done — keep it from regressing)*
**Done in this work:** backfilled R1–R3 actuals into `season_results_2026.json` + mirror; `forward_eval` now scores all 5 rounds with no fallback. **Guard:** the post-race phase already writes actuals going forward; add a CI check that `season_results` covers every completed round so the form features never silently degrade again.

### 5. Validate the wet-weather path before it's needed *(latent risk)*
**Why:** unexercised in production. **What:** backtest the wet Elo on historical wet races (data exists in `history.duckdb`, 2018–2025) so a rainy Monaco isn't its first live test. Low urgency unless the forecast turns.

## What NOT to do (evidence-based)
- **Do not keep tuning the pace ensemble** expecting completed-race gains. Report 2 shows it's a tie; the ceiling is structural. Japan (Report 1) proves the pace core already works when the race runs green.
- **Do not add new architectures speculatively.** The two highest-impact items (DNF rate, quali-NaN) are targeted fixes to known, reproduced failures — close those and re-measure before anything larger.

## Expected outcome if 1 + 2 land
- **Fix #2** removes the R1-class disasters (−14/−15 misses) outright — a clean, verifiable win.
- **Fix #1** won't raise position MAE much (DNFs still happen) but will materially improve **podium/win Brier and calibration** — the metrics that actually reflect a trustworthy prediction — and stop the model overclaiming on cars likely to retire. Re-run `diagnostics/rebuild.py` + `forward_eval` after each to quantify, exactly as in Report 2.
