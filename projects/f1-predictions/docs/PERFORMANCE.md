# RaceIQ — Model performance & evolution

This is the consolidated record of how the prediction model improved across its
development phases. Each phase was benchmarked with `benchmark_models.py compare`
over the 2024 + 2025 seasons (48 rounds). The detailed per-phase reports live in
[`docs/history/`](history/).

> **How to read this.** The headline metrics are **MAE** (mean finishing-position
> error, lower is better), **podium-hit** (share of actual podium finishers the
> model placed on the podium), and **winner-hit** (share of races whose winner
> the model ranked P1). "PROMOTE/REJECT" is the verdict of the phase's
> pre-registered promotion gate — a candidate had to clear an explicit bar, and
> several strong-looking candidates were honestly rejected for regressing on a
> protected metric.

## Evolution at a glance

| Phase | Change | MAE | Podium-hit | Winner-hit | Verdict |
|---|---|---:|---:|---:|---|
| Baseline | last-race-style re-rank | 5.87 | 32.6% | 14.6% | — |
| 1 | Per-circuit + hybrid blend | 5.07 | 32.6% | 14.6% | Tightened MAE only |
| **2** | **Elite podium/winner heads** | **4.95** | **45.8%** | **20.8%** | **PROMOTE** ✅ |
| 3 | 3-layer probabilistic engine | 5.00 | 46.5% | 18.8% | REJECT (winner −2.1pp) |
| 4 | Temporal-robustness layer | 4.98 | 45.8% | 18.8% | REJECT (winner −2.1pp) |
| 5 | Regime-routed architecture | 4.94 | 47.2% | 22.9% | REJECT (cold-start −6.2pp) |
| 6 | Mixture-of-experts gating | 4.94 | 47.9% | 20.8% | REJECT (no aggregate gain) |
| 7 | Weekend/telemetry features (static) | — | — | — | Production freeze |

The **Phase 2 elite heads** were the decisive jump: Phase 1 had driven MAE down
from 5.87 → 5.07 but podium-hit and winner-hit were stuck at baseline, because
those variants only re-ranked signals derived from the same predicted lap time.
Phase 2 added binary podium + winner classifier heads trained on elite-signal
features (prior-only per-driver podium/winner rates, per-circuit podium history,
qualifying-dominance gap) and broke the ceiling: **+13.2pp podium-hit, +6.2pp
winner-hit**.

Phases 3–6 explored richer architectures (probabilistic engine, temporal
robustness, regime routing, mixture-of-experts). Each was measured honestly
against the incumbent and against protected per-regime metrics; none cleared the
gate cleanly — regime routing in particular gained late-season winner-hit
(+12.5pp) but regressed cold-start (−6.2pp), which the gate treats as
disqualifying. The production model was ultimately frozen on the Phase-7 static
weekend-feature variant rather than chasing a regression-prone architecture.

## What "honestly gated" means here

- **No metric fishing.** Each phase declared its promotion criteria *before*
  running, and a candidate that improved the headline number while regressing a
  protected metric (e.g. cold-start winner-hit) was rejected.
- **Negative results are kept.** Phases 3–6 are documented as rejections, not
  buried. The detailed reports in [`docs/history/`](history/) include the
  per-season and per-regime breakdowns behind each verdict.
- **Approximation disclosure.** Some benchmark variants run on a synthetic
  feature frame rather than a full per-round retrain; those reports flag it
  explicitly as a *signal-direction* benchmark, not a production wiring.

## Forward evaluation (live)

Beyond these offline benchmarks, every shipped prediction is scored after the
race by [`forward_eval.py`](../forward_eval.py) against a `last-race-winner`
baseline, feeding the live [accuracy dashboard](https://roni-altshuler.github.io/f1_predictions/accuracy/)
and the drift + promotion gates. See
[`docs/MODEL_EVALUATION.md`](MODEL_EVALUATION.md) for that methodology.

## Detailed reports

- [Phase 1 — per-circuit + hybrid blend](history/BENCHMARK_PHASE_1.md)
- [Phase 2 — elite heads (PROMOTED)](history/BENCHMARK_PHASE_2.md)
- [Phase 3 — 3-layer probabilistic engine](history/BENCHMARK_PHASE_3.md)
- [Phase 4 — temporal robustness](history/BENCHMARK_PHASE_4.md)
- [Phase 5 — regime-routed architecture](history/BENCHMARK_PHASE_5.md)
- [Phase 6 — mixture-of-experts gating](history/BENCHMARK_PHASE_6.md)
- [Phase 7 — regime-routed (frozen variant)](history/BENCHMARK_PHASE_7.md)
