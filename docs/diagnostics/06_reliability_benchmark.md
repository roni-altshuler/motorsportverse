# Report 6 — Reliability / DNF Model: Benchmark, Feature Importance, Backtest

**Generated:** 2026-06-03 · **Priority 2.** Module: [`models/reliability_model.py`](../../models/reliability_model.py); benchmark harness: `diagnostics/reliability_benchmark.py`; tests: `tests/test_reliability_model.py` (11, passing).

## What was built

A reliability layer predicting, per driver per race: **`p_finish`, `p_dnf`, `p_mechanical`, `p_accident`**. DNF probability is a leakage-safe logistic regression (no class balancing → calibrated absolute probabilities) over an expanded feature set:

| Feature | Source | Learnable on this data? |
|---------|--------|-------------------------|
| `driver_hist_dnf_rate` | history.duckdb (career, prior-only) | ✅ |
| `driver_recent_dnf_rate` | rolling 10-race | ✅ |
| `team_dnf_rate` | team mapping + history | ✅ |
| `circuit_attrition_prior` | track-archetype SC probability | prior only |
| `street_circuit` | track-archetype | prior only |
| `rookie_factor` | prior-start count | ✅ |
| `weather_risk` | race rain probability | not in history rows |
| `power_unit_age` | **stub** (no PU data in repo) | neutral 0.0 |

**Mechanical vs accident split:** the available FastF1 `Status` in this dataset is coarse — only `Finished` / `Lapped` / `Retired` / `Did not start`, with **no** "Engine"/"Accident"/"Collision" granularity in either 2026 or the cached 2018–2025 seasons. A trained mechanical/accident classifier would therefore be fabricated. Instead the model splits `p_dnf` with a transparent circuit-conditioned prior (street circuits → accident-weighted 0.62, permanent → mechanical-weighted 0.62). `RetirementTaxonomy` + `learned_mechanical_fraction()` are implemented and unit-tested so the split is **learned automatically the moment granular `Status` data is supplied** — the infrastructure is ready; the labels are not present.

## Methodology validation (synthetic signal)

On synthetic histories with real structure, the model recovers it cleanly (`tests/test_reliability_model.py`): fragile drivers get materially higher `p_dnf` than reliable ones; probabilities are coherent (`p_finish + p_dnf = 1`, `p_mech + p_acc = p_dnf`); street circuits skew accident; a supplied granular-status set overrides the prior. **The model is methodologically sound.**

## Historical backtest vs production (2026 R1–5) — the decisive result

Ground truth: actual DNFs from FastF1 race `Status` (24 DNF/DNS across 110 slots). Brier score (lower = better):

| Estimator | Overall Brier |
|-----------|---------------|
| **base_rate (flat 0.15 — what the pace-only production implies)** | **0.175** ✅ best |
| `dnf_v1` (existing 2-feature `models/dnf.py`) | 0.201 |
| `reliability` (new expanded model) | 0.243 |

| Round | GP | Actual DNFs | base_rate | dnf_v1 | reliability |
|-------|----|-----:|----:|----:|----:|
| 1 | Australia | 5 | 0.18 | 0.19 | 0.22 |
| 2 | China | 7 | 0.25 | 0.30 | 0.37 |
| 3 | Japan | 2 | 0.09 | 0.13 | 0.15 |
| 4 | Miami | 4 | 0.15 | 0.20 | 0.24 |
| 5 | Canada | 6 | 0.21 | 0.19 | 0.25 |

**The flat base rate beats both DNF models on every round but one.** Reliability precision@k is at random expectation (top-5 risk → 1 actual DNF, top-10 → 2, top-15 → 3; random ≈ 1.1 / 2.2 / 3.3).

### Why: 2026 attrition has no learnable structure
- DNF rate is **0.20 in the predicted front half (P1–11) vs 0.24 in the back half (P12–22)** — essentially flat.
- Point-biserial correlation of DNF with predicted position: **r = 0.094, p = 0.33** (not significant).
- The discriminative features that work on real F1 (recent driver DNF rate, team reliability) carry the model — feature importance confirms it: `driver_recent_dnf_rate` (+7.79), `team_dnf_rate` (+2.10), `rookie_factor` (−2.10) — but those signals **do not transfer to 2026**, whose DNFs are statistically indistinguishable from a uniform-random draw across the field.

This is consistent with a **simulated 2026 season** whose retirements are assigned without the driver/team/position structure that historical reliability models rely on.

## Feature importance (logistic coefficients, signed log-odds)

```
driver_recent_dnf_rate   +7.79   (dominant — recent reliability)
team_dnf_rate            +2.10   (constructor reliability)
rookie_factor            -2.10   (rookies less DNF-prone in this history)
circuit_attrition_prior  -0.23
driver_hist_dnf_rate     -0.16
street_circuit            0.00   (constant in training → no learned weight)
weather_risk              0.00   (not present per history row)
power_unit_age            0.00   (stub)
```
`street_circuit`, `weather_risk` and `power_unit_age` cannot earn weight because `history.duckdb` has **no circuit, weather, or PU columns** per row — a data-schema limitation, not a model defect.

## Recommendation (evidence-based)

1. **Do NOT wire the reliability model into the production probability layer yet.** On 2026 data it would *worsen* calibration (Brier 0.243 vs 0.175). Keep the flat base rate for published win/podium probabilities.
2. **Use it for honest uncertainty, not point DNF claims.** Its real value is widening finish-range intervals on high-attrition rounds — pair with the volatility model (Report 7), not the pace ranking.
3. **The success criterion is data-limited.** "The next accuracy gain should come from reliability modeling" is **not achievable on the current (simulated) 2026 attrition**, because that attrition is unpredictable from any learnable signal. This is a property of the data, not the model. Re-run this benchmark (`python diagnostics/reliability_benchmark.py`) once real-season reliability data — or granular `Status` labels — are available; the module and taxonomy are ready.
4. **Schema follow-up:** to make circuit/weather/PU features learnable, add `circuit_key`, `status`, and (if obtainable) PU-age columns to `historical_predictions`. Without them the reliability ceiling is the base rate.

**Bottom line:** the reliability layer is correctly built, tested, and benchmarked. The benchmark's honest verdict is that it cannot beat the base rate on 2026 because those DNFs carry no predictable signal — exactly the kind of negative result that should stop us from shipping a model that looks sophisticated but degrades calibration.
