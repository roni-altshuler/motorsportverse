# Independent Ridge shadow audit

This is an offline experimental backtest and an unpublished shadow artifact.
It does not release Singapore’s publication hold, change original forecasts,
regrade history, write the serving registry or establish a live accuracy record.

## Coverage and source limits

The existing database supplies **1,836 actual-position records over 92 events** in 2022–2025.
Its prior-season predicted positions/lap times are excluded. They are neither
qualifying pace nor a final starting grid. Historical team, weather and status
fields are absent; current team assignments are not applied backwards.

Only 2026 rounds **2–11 and 15** contain the same complete qualifying/grid
field plus actual classification. Round 1 has only 19 qualifying rows; rounds
12–13 lack grid fields; round 14 has only 20 qualifying rows; Sepang round 16
has no qualifying/grid snapshot. No grid is reconstructed from qualifying order.
Historical final grids come from committed race-result grid fields: these are
reconstructed pre-race facts, not immutable forecasts captured before each race.
The stored-model baseline also includes retrospective regenerations.

Weather and sprint-result features/interactions are omitted because historical
forecast issue and source-availability timestamps are not recorded. DNF status
is absent in the historical database; a last-place finish is not labelled DNF.
Missing qualifying or history values use training-fold median encoding with
explicit missingness indicators inside the model. No factual source field is filled.

## Evaluation

The first five eligible events train the initial fold; every subsequent event
is held out with all of its drivers. Every aggregation and fit uses strictly
earlier events. Median encoding and StandardScaler are fitted within each fold.
Ridge alpha is fixed at 10 before evaluation; no temperature or target-event
outcome enters a feature, hyperparameter choice or calibration. No probabilities
are produced. Driver recent form uses five prior classifications; driver/track
form uses three. Team form uses three prior events with recorded team identity.
Sepang does not share Sakhir/Bahrain venue history.

The common test cohort is **six events: 7, 8, 9, 10, 11 and 15; 132 drivers**.
These are retrospective diagnostics over saved data, not forward-time calls.

| Method | Position MAE ↓ | Spearman ↑ | Winner hits / 6 |
|---|---:|---:|---:|
| Final-grid baseline | 3.258 | 0.689 | 4 |
| Qualifying-order baseline | 3.152 | 0.723 | 4 |
| Stored-model snapshot baseline | 3.197 | 0.729 | 3 |
| Ridge: grid only | 3.258 | 0.689 | 4 |
| Ridge: qualifying + grid | 3.212 | 0.701 | 4 |
| Ridge: qualifying + grid + prior history | 3.303 | 0.696 | 4 |

**No promotion.** The history challenger has higher MAE than the final-grid
and stored-model baselines on this small shared cohort. Extra podium overlap
does not override the regression or the missing historical availability record.
Data loading plus backtest took **1.02 seconds** with one CPU thread.
[Machine-readable evaluation, per-event metrics and input hashes](evaluation.json).

## Singapore today

[The immutable shadow artifact](candidate_20261011T063852Z_70312c902a22.json) was generated at `2026-10-11T06:38:53.000555Z`
with input cutoff `2026-10-11T06:38:52.168248Z`. It pins model SHA `70312c902a22ee0b2cf1b2eb97c003c0de1acb9fe5adba5c162ea84ccc4935c9`,
implementation SHA and the exact input source hashes. Its official qualifying
and grid source-check times are recorded separately from the original withdrawn
forecast time. The artifact is labelled `shadow_only`, has no probabilities and
does not release the hold. Source snapshots are available locally before this
new cutoff; that does not establish historical input cutoffs for the backtest.

Russell’s official qualifying position is 6 and final grid is 21. Both are
separate model inputs. His penalty delta exceeds the training range, and that
extrapolation is explicitly recorded. The numerical shadow estimate is not a
reviewed replacement forecast.

The verified race start is **12:00 UTC / 20:00 Singapore on 11 October**.
The evidence-backed option is to keep the official grid/session display and
withdrawal while independent review continues. A replacement needs verified
inputs, measured improvement, an immutable artifact and a separate publication
path that validates before any serving/feature-state write. This candidate
does not meet the measured promotion gate.

## Reproduction and safety

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python src/ridge_shadow.py --candidate-round 17
```

Writes are restricted to `reports/ridge-shadow/`. Complete JSON is staged and
atomically created without overwriting. Existing artifacts and all serving/
feature forecasts are preserved. A source-code change, target outcome, missing
source time or race deadline rejects the candidate. Negative tests cover these
boundaries, whole-event folds, prior-only history and fold-local scaling.

This branch is separate from the identity repair and depends on its reviewed
calendar/hold changes. No provider requests, paid services, credentials or
production jobs were used. No creator’s code or accuracy claim was copied.

Local verification: **1,148 Python tests passed, 15 skipped**;
**13 Ridge regressions passed**. Ruff passed. Input hashes still match every
source file, and the identity-repair worktree remains unchanged. No site code
changed, so no new browser journey is introduced. [Validation record](validation.json).
