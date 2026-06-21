# Report 2 — Current-Model vs Original-Model Comparison

**Generated:** 2026-06-03 · **Question:** *Would the current (frozen) production model have done better than the model version that generated the published predictions?*

## Method

Re-ran the **current code** for rounds 1–5, fully sandboxed (`diagnostics/rebuild.py`, `persist_output=False`, registry no-op, `save_predicted_result` monkeypatched, offline cache). Two variants:

- **frozen** — round-to-round feedback features read the committed prior predictions (isolates *code* changes from *data* changes).
- **rechain** — `PREDICTED_RESULTS_FILE` redirected to a scratch chain built from the rebuilt predictions (tests end-to-end self-consistency).

Scored with `forward_eval.score_round` / `evaluate_season` against authoritative actuals. The "original" baseline is `predicted_results_2026.json`, which `forward_eval` confirms reproduces `season_tracker` accuracy exactly (R1 MAE 6.36, within-5 13 → identical), so it is the true published prediction.

## Result — original vs current vs actual

| R | GP | Original MAE | Current MAE (frozen) | Current MAE (rechain) | Δ | Order match (current vs original) |
|---|----|--------------|----------------------|-----------------------|---|-----------------------------------|
| 1 | Australia | 6.36 | 6.36 | 6.36 | 0.00 | **22/22 identical** |
| 2 | China | 4.64 | 4.55 | 4.55 | −0.09 | 18/22 (mean Δpos 0.18) |
| 3 | Japan | 2.00 | 2.00 | 1.91 | 0.00 / −0.09 | **22/22 identical** |
| 4 | Miami | 4.18 | 4.27 | 4.36 | +0.09 | 17/22 (mean Δpos 0.27) |
| 5 | Canada | 5.36 | 5.36 | 5.36 | 0.00 | **22/22 identical** |
| | **Aggregate** | **4.51** | **4.51** | **4.51** | **0.00** | — |
| | Total within-5 | 83/110 | 83/110 | 83/110 | 0 | — |

## Findings

1. **The current model reproduces the original predictions almost exactly.** Three of five rounds (R1, R3, R5) are **bit-identical** (22/22 drivers same position). R2 and R4 differ by trivial reorderings (mean position change 0.18 and 0.27); R4's only visible change is a top-3 swap (rebuild: VER-RUS-NOR vs original RUS-NOR-VER).

2. **Net accuracy improvement: zero.** Aggregate MAE is **4.51 in both directions**; total within-5 is **83/110 in both**. The two micro-deltas cancel (R2 −0.09, R4 +0.09). By every position metric the current model is a statistical tie with the version that made the published calls.

3. **This is not a flaw in the comparison — it is the finding.** The completed-race errors live almost entirely in **DNFs and the R1 qualifying-NaN event** (Report 1). None of the model improvements since these rounds (ensemble re-weighting, Elo features, game-theory post-processing, calibration) target retirement risk or no-time qualifying, so they cannot move the completed-race numbers. The improvements may help *probability calibration* and *clean-race ordering*, but on these specific races the ceiling is set by attrition the model cannot see.

4. **Reproducibility is excellent** — a useful secondary result. Running current code on frozen history regenerates the frozen predictions to the position, confirming the pipeline is deterministic and the registry-free retrain path is stable. The small R2/R4 drift comes from round-to-round feature feedback sensitivity, not nondeterminism.

## Bottom line

**No — the current model would not have performed measurably better on rounds 1–5.** It is neither better nor worse (MAE 4.51 vs 4.51). Genuine accuracy gains on these weekends require modelling what currently has *no representation*: **DNF/reliability risk** and **robust qualifying-data handling** — see Report 5. Continuing to tune the pace ensemble will not change this until those structural gaps are closed.

*Artifacts:* `diagnostics/rebuild_2026/predicted_rebuilt_{frozen,rechain}_2026.json`, per-round metrics in `diagnostics/rebuild_2026/metrics/`, run logs `run_{frozen,rechain}.log`.
