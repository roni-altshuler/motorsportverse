# Continued model and fan-experience improvements

Implemented 2026-09-18, following the initial platform audit. MotorsportVerse
remains a motorsport product; the sports-and-AI vision is expressed through
useful exploration, visible evidence and forecasts that obey the sport's rules.

## Model findings and changes

**Independent calibration can make mutually inconsistent claims.** Correct
market totals alone do not ensure that a driver's win probability is below
their podium probability. Shared export normalization now jointly projects
same-field win/podium/top-six/top-ten probabilities onto those constraints.
It preserves column totals and bounds, uses deterministic Dykstra projections,
and fails if convergence cannot be established. Unknown markets and different
fields are not combined. Raw simulation probabilities are preserved.

The bounded scaling step also lost mass when positive entries saturated while
zero entries were pinned to the floor. The corrected implementation redistributes
that residual mass; all-zero markets still remain absent signals.

The in-memory replay of existing exports found:

| Series | Market blocks | Contradictions before | After |
| --- | ---: | ---: | ---: |
| F2 | 28 | 14 | 0 |
| F3 | 18 | 76 | 0 |
| Formula E | 17 | 6 | 0 |
| IMSA | 30 | 0 | 0 |
| IndyCar | 18 | 54 | 0 |
| MotoGP | 44 | 63 | 0 |
| NASCAR | 36 | 98 | 0 |
| WEC | 13 | 3 | 0 |
| WRC | 14 | 145 | 0 |
| **Total** | **218** | **459** | **0** |

A contradiction is one competitor's larger probability for a narrower adjacent
market. These are market blocks, not independent races: sprint/feature sessions
and endurance classes can contribute multiple blocks. Some tiny adjustments
also remove rounding drift. The largest adjustment is about 9.67 percentage
points; the largest residual mass error is below 1e-14 before export rounding.
The F1 flagship has a separate implementation and is excluded from this replay.

This is a **consistency repair, not evidence of improved forecast accuracy**.
The audit never overwrites historical data. Future exports using the shared
normalizer receive the repair. The chronological F2/F3 skill candidate remains
opt-in; the prior small-sample result still does not support promoting it.

Reproduce from the repository root:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  scripts/audit_probability_coherence.py \
  --output docs/research/probability-coherence-audit.json
```

**Uncertainty refits could retain old strata.** Conformal refits now clear both
stratum and global state, including after invalid fitting input. The empirical
threshold uses the exact finite-sample residual rank. A request for coverage
that requires a rank beyond the available sample raises explicitly instead of
clipping to the largest observed residual and implying unsupported coverage.
Sparse strata fall back to the newly fitted global interval. Inputs must be
finite one-dimensional arrays. Racing data still needs out-of-time coverage
measurement; exchangeability is not established by this implementation.

**Championship exports rounded away probability mass.** The broader CI run
exposed a MotoGP title distribution summing to 1.0002 after per-driver rounding.
Shared championship serialization and the seven affected series exporters now
retain simulation precision. Percentage formatting remains a presentation concern.
The existing strict distribution test stays intact.

## Fan experience

- The race summary shows the next seven days, available upcoming forecasts and
  series coverage. A forecast-only filter reduces searching through empty races.
- The favourite-versus-field strip shows how much probability lies outside the
  leading driver; the full-field control makes every published driver accessible.
- Driver comparison shows win/podium chances, a percentage-point difference and
  a clear explanation that marginal probabilities are not head-to-head odds.
- The whole podium column is unavailable if its competitor set, total or nesting
  is invalid. The client does not invent or silently repair published forecasts.
- Race links restore the selected race and calendar view after navigation. Copy
  failure exposes the actual link as selectable text. Favourites stay local.
- A short expandable probability guide explains the numbers. Evidence and
  calibration status remain visible beside the exploration controls.

## Verification

The numerical tests compare the joint solution with an independent constrained
optimizer and exercise small/large fields, permutation invariance, bounds,
market totals, idempotence, zero support and raw-data preservation. Conformal
regressions cover exact ranks, impossible finite coverage and stale refits.
Frontend tests cover comparison selection, full-field expansion, missing podium
data, shared links and filter transitions. The browser script additionally
checks clipboard sharing, reload/navigation and desktop/mobile rendering.

All six frontend suites passed: 73 tests with eight existing skips. Focused
numerical regressions, Python lint and shared UI synchronization also passed.
The complete package/project suites and browser verification gate publication
to main; CI provides the revision-specific result.

## Next evidence-driven priorities

1. Measure out-of-time Brier/log loss before and after the consistency repair,
   by event and market, on immutable pre-race snapshots. Consistency alone does
   not establish calibration quality.
2. Expand genuine multi-season result coverage before tuning the chronological
   skill candidate. Reserve outer seasons/events for final evaluation and
   compare against qualifying, recent form and standings on identical fields.
3. Publish empirical interval coverage by season, weather and experience group;
   avoid confidence labels that conceal missing or insufficient observations.
4. Add actual session timestamps and reliable result ingestion before countdowns
   or live-state claims. Preserve missing-result and stale-data states.
5. Extend driver comparisons to actual head-to-head simulation outputs only when
   those joint outcomes are exported and validated; never derive them by dividing
   marginal win probabilities.

References: [scikit-learn probability calibration](https://scikit-learn.org/1.8/modules/calibration.html)
for proper-score assessment and [Angelopoulos and Bates](https://arxiv.org/abs/2107.07511)
for conformal prediction assumptions and finite-sample construction.
