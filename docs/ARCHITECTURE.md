# RaceIQ — Architecture

This document describes how RaceIQ is built today (the three-layer prediction
pipeline + the static dashboard) and, at the end, the **target architecture**
the codebase is converging toward.

## Three-layer prediction pipeline

The system has three parallel pathways. Layers 1 + 2 are always-on; layer 3 is opt-in via `--use-race-simulator`.

```
                ┌───────────────────────────────────────────────┐
                │  Historical race archive (1950–2025)          │
                │  data/history.duckdb                          │
                └────────────────────┬──────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ Layer 1          │   │ Layer 2          │   │ Layer 3          │
    │ Per-race lap-    │   │ Probability      │   │ Per-lap Monte    │
    │ time regression  │──▶│ sampler +        │──▶│ Carlo race       │
    │ (GB + XGB)       │   │ isotonic         │   │ simulator        │
    └──────────────────┘   │ calibration      │   └──────────────────┘
              │            └──────────────────┘             │
              ▼                      │                      │
    ┌──────────────────┐             │                      │
    │ Bootstrap 90%    │             │                      │
    │ prediction       │◀────────────┘                      │
    │ intervals        │                                    │
    └──────┬───────────┘                                    │
           │                                                │
           ▼                                                ▼
    ┌──────────────────────────────────────────────────────────┐
    │ website/public/data/rounds/round_NN.json                 │
    │   classification[*] = {                                  │
    │     predictedTime,                                       │
    │     winProbability, podiumProbability,                   │
    │     predictionIntervalLow / High,                        │
    │     simulatorWinProbability,                             │
    │     dnfProbability  ← new in Phase 1                     │
    │   }                                                      │
    └──────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Next.js dashboard
```

### Layer 1 — per-race regression
[`f1_prediction_utils.py::train_ensemble`](../f1_prediction_utils.py) trains a Gradient Boosting + XGBoost ensemble per race, target = `AdjustedQualiTime`. Features include circuit characteristics, prior-round driver/team form, qualifying gap, pit-strategy expectations, tyre degradation factors, weather inputs (38 features total).

Ensemble weights are computed per race from inverse-MAE on held-out drivers. An optional LSTM lap predictor contributes a small ~10-18% weight when PyTorch is available.

### Layer 2 — probability sampler + calibration
[`models/calibration.py`](../models/calibration.py) reads predicted lap times and runs a Plackett-Luce sampler via the Gumbel-max trick (5000 MC samples, deterministic seed) to produce per-driver `p_win`, `p_podium`, `p_top6`, `p_top10`, plus the head-to-head matrix.

Isotonic regression calibrates the raw probabilities using `(predicted_p, observed_outcome)` pairs from `data/history.duckdb`. A `StratifiedProbabilityCalibrator` extends the basic isotonic with per-market stratification and a global fallback.

**Honest gating**: `calibration.applied = false` until the history contains ≥ `--min-completed-rounds` distinct `(season, round)` tuples. When uncalibrated, the website surfaces a banner; when calibrated, it surfaces a green "Calibrated" badge.

### Layer 3 — per-lap Monte Carlo race simulator (opt-in)
[`models/race_simulator.py`](../models/race_simulator.py) iterates lap-by-lap predictions per driver, maintaining running gaps + positions, sampling pit-stop laps, injecting Safety Car events from a Poisson process. 2000 MC samples by default. Trained offline via [`train_race_pace.py`](../train_race_pace.py); persisted under `models/registry/<season>_round_99/`.

When active, splices `simulatorWinProbability` / `simulatorPodiumProbability` / `simulatorMeanFinish` into each classification entry plus a `modelConfig.raceSimulator` block.

**Phase 1 addition**: per-driver DNF sampling. [`models/dnf.py`](../models/dnf.py) trains a logistic regression on historical mechanical/strategy DNFs; the simulator now samples `Bernoulli(p_dnf)` per driver per simulation and excludes DNF'd drivers from final position calculations.

## Data flow

**Python → JSON → TypeScript** contract. The contract lives at:
- [`website/src/types/index.ts`](../website/src/types/index.ts) — TypeScript interfaces (frontend source of truth).
- [`tests/test_website_data_schema.py`](../tests/test_website_data_schema.py) — pydantic mirror (CI gate).

When you change a Python output, update the matching TS type and pydantic mirror **in the same change**.

Key data files under `website/public/data/`:

| File | Contents |
|---|---|
| `season.json` | Calendar, drivers, teams, completed rounds, sprint flags |
| `standings.json` | Driver + constructor standings, `pointsHistory`, `wdcPossibility` |
| `rounds/round_NN.json` | Predicted classification, bootstrap intervals, simulator probabilities, weekend sessions, model metrics, weather |
| `probabilities/round_NN.json` | Probability layer outputs + calibration summary |
| `forward_eval/round_NN.json` | Per-round accuracy metrics |
| `model_health.json` | Feature drift + rolling Brier |
| `promotion_status.json` | Shadow / A-B promotion decision |
| `gp_accuracy_report.json` | Season-rolling accuracy (powers the navbar accuracy chip) |

## Frontend dashboard

Next.js 16 static-export (`output: "export"` in [`next.config.ts`](../website/next.config.ts)) — no server components, no API routes, no runtime fetches against secrets. Everything is built at deploy time from the JSON snapshots above.

Key pages:
- `/` — home with featured race + podium predictions
- `/race/[round]` — race detail with weekend sessions, deep dive, interactive charts
- `/standings` — drivers + constructors tabs + "Who Can Still Win" math
- `/calendar` — all 22 races with circuit aerial photography
- `/accuracy` — round-over-round model performance + calibration panel

Design system: Bugatti palette (dark theme primary), 11-team color tokens via `[data-team="..."]`, motion tokens via CSS variables. See [`website/src/styles/tokens.css`](../website/src/styles/tokens.css) for the full token list.

## Continuous-learning infrastructure

| Module | Role |
|---|---|
| [`models/registry.py`](../models/registry.py) | File-backed model registry. Binaries gitignored; `metadata.json` committed. |
| [`forward_eval.py`](../forward_eval.py) | Per-round metrics (MAE, Brier-vs-uniform, Spearman, NDCG@5) + a `last_race_winner` baseline. |
| [`models/drift.py`](../models/drift.py) + [`drift_report.py`](../drift_report.py) | PSI per feature against a baseline + rolling-Brier trend. Severity bands: PSI 0.10/0.25, Brier 5%/15% regression. |
| [`models/promotion.py`](../models/promotion.py) + [`promotion_decision.py`](../promotion_decision.py) | Guarded production/candidate comparison. Requires ≥5 overlapping rounds + 2% mean improvement + no per-round 20%+ regression before recommending promote. |
| [`models/online_game_theory.py`](../models/online_game_theory.py) | Ridge-regression learner for game-theory coefficients in `RaceProjectionScore`. Registry sentinel round 98. |

## Target architecture (north star)

The pipeline grew organically: today the Python entry points live as ~40 scripts
at the repository root, wired directly into the cron CI workflows and the test
suite. That works and is intentionally left in place — moving load-bearing entry
points would break the live deploy. But the **intended** module boundaries, which
new code should respect and which a future refactor should converge toward, are:

```
raceiq/
├── core/        Pure domain logic — no I/O. Pipeline math, scoring, leakage
│                guards, calibration, intervals. (today: models/, leakage.py,
│                f1_prediction_utils.py internals)
├── services/    Orchestration + side effects. Data ingestion, backfill, the
│                export pipeline, registry, drift/promotion. (today:
│                export_*.py, *_backfill.py, drift_report.py, promotion_decision.py)
├── data/        Storage adapters — DuckDB history, JSON contract writers,
│                caches. (today: data/, the JSON-writing parts of export_*.py)
├── lib/         Shared cross-cutting helpers (config, env, logging, dates).
├── cli/         Thin argument-parsing entry points that call services/.
│                (today: the top-level scripts ARE the CLI)
└── ui/          The Next.js dashboard. (today: website/)
```

**Guiding rules for new code (apply now, even before any physical move):**

- **No I/O in `core`-style logic.** Keep pure functions (math, scoring,
  transforms) free of file/network access so they stay unit-testable. The
  existing `models/` package already mostly follows this.
- **Side effects live in services / CLI.** Argument parsing, file writes, and
  API calls belong in the entry-point scripts, not in the math.
- **One contract, two mirrors.** The Python↔website contract is
  `website/src/types/index.ts` + the pydantic mirror in
  `tests/test_website_data_schema.py`. Changes touch both together.
- **The website is a leaf.** It only ever reads the JSON snapshots; it never
  reaches back into Python.

The current root-level layout maps onto these boundaries by responsibility (see
the comments in the tree above), so the target is a **reorganization, not a
rewrite** — to be done incrementally and only alongside the corresponding CI /
test / `CLAUDE.md` path updates. See [`REBRAND.md`](REBRAND.md) for the related
set of deferred, deploy-coupled changes.
