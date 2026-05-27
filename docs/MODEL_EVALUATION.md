# Model evaluation methodology

## Why forward-eval, not random splits

The per-race [`train_ensemble`](../f1_prediction_utils.py) returns same-race metrics (4 held-out drivers from the same race) — useful for ensemble weighting, **not** for forward generalization. Random splits across rounds would create temporal leakage because driver/team form features aggregate prior rounds; a model trained on round 5 has implicitly seen rounds 1-4, so testing it against round 3 lets it cheat.

The real validation surface is [`forward_eval.py`](../forward_eval.py).

## Metrics per round

For each completed round, [`forward_eval.py`](../forward_eval.py) reads the predicted classification from `website/public/data/rounds/round_NN.json` and the actual classification from `season_results_2026.json`, then computes:

| Metric | Range | What it tells you |
|---|---|---|
| MAE (position) | ≥ 0 | Mean absolute position error across 22 drivers |
| Spearman ρ | [-1, 1] | Rank correlation; 1 = perfect ordering |
| Brier (vs uniform) | ≥ 0 | Probability calibration vs uninformed baseline |
| NDCG@5 | [0, 1] | Top-5 ordering quality |
| Podium hits | [0, 3] | How many podium predictions matched |
| Exact-position hits | [0, 22] | Drivers placed at their predicted exact position |

Plus a **baseline** computed in parallel: `last_race_winner` — predicts whoever won the previous round to win again, last grid order otherwise. A good prediction model should beat this baseline on every metric.

Output written to `website/public/data/forward_eval/round_NN.json` per round, and aggregated for the `/accuracy` dashboard.

## Drift report

[`drift_report.py`](../drift_report.py) → `website/public/data/model_health.json`.

- **Feature PSI** per feature against a baseline (typically the first 3 rounds of the season). Severity bands: warning at PSI 0.10, alarm at 0.25.
- **Rolling Brier** trend over the last N rounds. Warning if 5% worse than baseline, alarm at 15% regression.
- Both surface to the `/accuracy` dashboard as chips.

## Promotion gate

[`promotion_decision.py`](../promotion_decision.py) → `website/public/data/promotion_status.json`.

Compares a candidate model stream against the production stream. Requires:
- ≥ 5 overlapping rounds of forward-eval results.
- ≥ 2% mean MAE improvement.
- No per-round regression of ≥ 20%.

When the gate trips, the workflow can promote the candidate to production. Until then, the candidate runs in shadow.

## Calibration audit

When `calibration.applied = true`, the calibration summary at `website/public/data/probabilities/calibration_summary.json` reports:

- Calibration slope (perfect = 1.0).
- Calibration intercept (perfect = 0.0).
- Per-market reliability curve points (15 bins of predicted probability vs observed frequency).

These render to the `/accuracy` Calibration panel ([`CalibrationPanel.tsx`](../website/src/components/CalibrationPanel.tsx)).

## Phase 1 benchmark

[`docs/BENCHMARK_PHASE_1.md`](BENCHMARK_PHASE_1.md) — quantitative before/after of the Phase 1 ML overhaul (multi-season calibration backfill + DNF probability model + race simulator CI wiring + bootstrap intervals surfaced).

Compares three streams across rounds 1-5:
1. `last_race_winner` baseline.
2. Pre-Phase-1 production model.
3. Post-Phase-1 model (calibration + DNF + simulator).

## Determinism testing

`pytest tests/test_simulator_determinism.py` runs the race simulator twice on the same grid with the same seed and asserts `np.allclose(probs_run_1, probs_run_2)`. Identical inputs must produce identical outputs across runs.

## Ablation testing

`forward_eval.py --ablation` (planned, see [docs/ROADMAP.md](ROADMAP.md)) runs the pipeline with each feature held constant (at its training-set median) and measures MAE delta per feature. Surfaces the 5 highest-impact features per round, plus the 5 features whose removal does the least damage (candidates for pruning).
