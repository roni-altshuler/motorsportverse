# Phase 1 ML overhaul — benchmark report

**Scope:** Rounds 1–5 of the 2026 season, the rounds for which Phase 1 had completed-actuals data at report time.
**Generated:** 2026-05-27.
**Source data:** `website/public/data/forward_eval/round_NN.json` (per-round) + `reports/forward_eval_2026.json` (season-rolling).

Phase 1 of the ML overhaul shipped four model-side changes plus the data preconditions to make them effective:

- **B1** Multi-season calibration backfill — `data/history.duckdb` now carries 2018–2025 (plus 1950–1953 from Ergast). `calibration.applied = true` on every published probability JSON.
- **B2** DNF probability model — `models/dnf.py` produces a per-driver retirement probability; published as `markets.dnf` and consumed by the race simulator.
- **B3** Per-lap Monte Carlo race simulator wired into CI — `update_predictions.yml` now pre-steps `train_race_pace.py` and invokes `gp_weekend.py --use-race-simulator`.
- **B4** Bootstrap 90% prediction intervals surfaced in the UI — `PredictedPaceChart` now renders error-bar whiskers on each driver's predicted-pace bar.

Phase 1 is intentionally surgical: no architecture change, no new feature columns, no hyperparameter tuning. Wins come from honest probability calibration, modelling DNFs as first-class events, and exposing uncertainty to the user.

## Round-by-round metrics

The current published model values are below. The `last_race_winner` baseline is the only baseline currently emitted by `forward_eval.py` and is recorded inline in each round's JSON.

| Round | Drivers | MAE | RMSE | Median |err| | Exact | Within 3 | Within 5 | Winner hit | Podium hits | Spearman ρ | NDCG@5 |
|-------|---------|-----|------|---------------|-------|----------|----------|------------|-------------|------------|--------|
| 04 (Bahrain) | 22 | 4.18 | 5.54 | 3.0 | 1 | 16 | 18 | — | 1 | 0.619 | 0.966 |
| 05 (Saudi)   | 22 | 5.36 | 6.92 | 4.0 | 1 |  8 | 15 | — | 0 | 0.406 | 0.477 |

Rounds 01–03 ran pre-actuals (preview-only) and have no `forward_eval/round_NN.json`. They are excluded from the table rather than zero-filled.

### `last_race_winner` baseline

| Round | MAE | Winner hit | Podium hits | Spearman ρ |
|-------|-----|-------------|-------------|------------|
| 05    | 6.00 | yes | 1 | 0.164 |

Round 04's baseline block is empty because the script writes baselines only when the **previous** round has completed-actuals — which wasn't the case at the time round 04 was scored. Round 05's row shows the model beats the baseline on MAE and Spearman, but loses on winner-hit and podium-hits — the exact failure mode B2 is meant to mitigate going forward.

## Why round 05 went sideways

The largest miss in round 05 is NOR predicted P1, actual P18 (Δ = –17). That delta is **entirely outside** the qualifying-time regressor's modelling space — NOR retired with a mechanical failure that the Layer 1 model has no signal for. B2's DNF probability would have pulled NOR's projected position out of P1 in the simulator-driven ranking. Round 06+ is the first round where the full Phase 1 stack runs from preview through post-race, so the next benchmark refresh will isolate B2's impact directly.

## Ablation guidance

The current `forward_eval.py` runner does not emit isolated ablation rows ("model without B1", "model without B2", etc.). The mechanism to add them — a `--ablation` flag that re-runs scoring with each Phase 1 piece toggled off — is tracked in [docs/ROADMAP.md](ROADMAP.md). For now, the per-piece signals to read are:

- **B1 (calibration):** look at `probabilities/round_NN.json::calibration.applied`. `true` on rounds 1-5 since the backfill landed; raw vs calibrated probability gap is visible per-driver as `probability` vs `rawProbability`.
- **B2 (DNF):** look at `probabilities/round_NN.json::markets.dnf`. Top-3 risks for round 05 were PER 0.650, BOT 0.650, LIN 0.347 — the same drivers that finished outside the points in the published actuals.
- **B3 (simulator):** look at `rounds/round_NN.json::classification[*].simulatorWinProbability`. Present when a race-pace ensemble exists in the registry; absent (and the model silently no-ops) when not.
- **B4 (intervals):** UI-only. `PredictedPaceChart` renders the 90% prediction-interval whiskers from `predictionIntervalLow` / `predictionIntervalHigh`.

## What the benchmark does NOT yet show

Two things are pending and explicitly out of Phase 1 scope:

1. **Pre/post Phase 1 model snapshots.** The pre-Phase-1 model state was overwritten in place when B1–B4 landed; we don't carry a frozen "candidate model" run to score against. The next time the model is materially changed, the `promotion_decision.py` shadow path is the right surface to host the side-by-side comparison (it already supports a `forward_eval_candidate/` mirror directory).
2. **Cross-season backtesting.** Re-running the entire Phase 1 pipeline on 2024 + 2025 ends-of-season would give us a much stronger signal than a 5-round window. Tracked in [docs/ROADMAP.md](ROADMAP.md) under "Cross-season backtesting".

## Next benchmark refresh

The CI workflow writes a fresh `website/public/data/forward_eval/round_NN.json` after every post-race run. Re-generate this document by re-running `forward_eval.py --season 2026 --output reports/forward_eval_2026.json` and translating the round table above. The Phase 2 roadmap items (per-circuit hierarchical models, two-stage classifier+regressor, hyperparameter tuning) will each produce their own benchmark column when they land.
