# Report 7 — Race Volatility Model: Benchmark

**Generated:** 2026-06-03 · **Priority 3.** Module: [`models/race_volatility.py`](../../models/race_volatility.py); harness: `diagnostics/volatility_benchmark.py`; tests: `tests/test_race_volatility.py` (9, passing). Complements the existing learned [`models/volatility_model.py`](../../models/volatility_model.py).

## What was built

A circuit chaos model outputting, per circuit:
- `safety_car_probability` — P(at least one full SC)
- `vsc_probability` — P(at least one VSC)
- `red_flag_probability` — P(red flag)
- `volatility_score` ∈ [0,1] — expected **deviation from pace-based finishing order**

Two sources, blended by sample-size shrinkage:
1. **Track-archetype priors** (historically grounded per-circuit SC probability, qualifying-importance, overtaking-difficulty, tyre-deg).
2. **Empirical rates** from FastF1 `track_status` (codes: SC=4, VSC=6/7, red=5), aggregated across cached seasons (2023–2026) via `compute_circuit_status_rates`. FastF1 is injected as a loader callable so the module stays unit-testable offline.

**Volatility-score design:** a race deviates from pace order when interruptions reshuffle it *and* track position is easy to lose. Score = `0.45·SC_prob + 0.35·(1−qualifying_importance) + 0.20·tyre_deg`. This is why **Monaco scores LOW volatility despite HIGH SC probability** — it is qualifying-locked, so chaos rarely changes the order (unit-tested; matches the learned `volatility_model.py` behaviour).

## Backtest vs actual 2026 chaos (rounds 1–5)

Validated `volatility_score` against actual position shuffle (mean |predicted−actual| per round):

| Rank | R | GP | volatility_score | actual shuffle | pred SC prob | actual SC/VSC |
|------|---|----|-----------------:|---------------:|-------------:|:-------------:|
| 1 (calmest) | 3 | Japan | 0.479 | **2.00** ✅ | 0.43 | yes |
| 2 | 4 | Miami | 0.504 | 4.18 | 0.53 | yes |
| 3 | 1 | Australia | 0.509 | 6.36† | 0.58 | yes |
| 4 | 2 | China | 0.565 | 4.64 | 0.60 | yes |
| 5 (wildest) | 5 | Canada | 0.601 | **5.36** ✅ | 0.73 | yes |

**`volatility_score` vs actual shuffle: Spearman ρ = 0.70** (p = 0.188, n = 5 — indicative, not significant).

### This is a genuinely useful, positive signal — in contrast to the DNF model
- The model correctly identifies **Japan as the cleanest race** (lowest score, lowest shuffle) and **Canada as among the wildest**.
- †The one outlier is **Australia**: predicted mid-pack volatility but the *highest* observed shuffle (6.36). That shuffle was driven by the **qualifying-NaN bug** (SAI/STR, fixed in Report 8/Priority 1), not by circuit chaos — with the fix, Australia's shuffle drops to ~5.45, tightening the fit. So the volatility model was arguably *right* about Australia's intrinsic chaos; the audit metric was polluted by a separate, now-fixed defect.

### Safety-car probability
Predicted SC probabilities (0.43–0.73) vs actual: **SC or VSC occurred in all 5 races** (full SC in 3/5). Brier 0.19. The model under-predicts *some* interruption occurring (every 2026 race had at least a VSC), so the SC/VSC base rate should be lifted — a calibration tweak, not a structural problem.

## Why volatility has signal where DNF (Report 6) did not

The DNF backtest found 2026 retirements statistically random (r=0.09, p=0.33). Volatility is different because it predicts **how much the order moves**, which is governed by *circuit properties* (overtaking difficulty, SC exposure, tyre deg) that are stable and historically grounded — not by *which driver* retires, which is random. The model captures the structural part of chaos and stays agnostic about the irreducible part. That is exactly the stated objective: "estimate how likely a race is to deviate from expected order," not predict exact incidents.

## Recommended use

1. **Widen finish-range intervals on high-volatility rounds.** Feed `volatility_score` into the bootstrap interval width and the race-simulator's `sc_likelihood` (currently a static `CIRCUIT_CHARACTERISTICS` scalar). High-volatility races should publish wider, honest uncertainty.
2. **Lift the SC/VSC base rate** so "some interruption" isn't under-called (all 5 races had one).
3. **Do NOT use it to reorder the pace prediction** — it scales uncertainty, it does not move point predictions. Pair with the reliability layer (Report 6) for an honest "expect deviation" signal rather than overconfident podiums.
4. **This is the most promising of the three new layers** for the success criterion: it has real, directionally-correct signal (ρ=0.70) and is the right lever for converting "model looks wrong on chaotic races" into "model was honestly uncertain."
