# Motorsportverse: model and fan experience audit

Audit date: 2026-09-18. Starting revision after pulling main: `5f3116e`.

## Findings and implemented changes

1. **The hub's live ticker was synthetic.** `synthTickerRows` generated driver
   names, percentages and trends with a seeded PRNG and labelled operational
   series “live”. The ticker and generator are removed. The new race centre
   reads committed calendars, driver rosters, probabilities and evidence at
   build time. It matches forecast season and round, validates win-market mass,
   and never substitutes class-win probabilities for an overall win.
2. **The hub led with software infrastructure, not racing.** The homepage now
   leads with a calendar, series filters, race/circuit search, saved following,
   win/podium probabilities and a model-versus-baseline panel. Results,
   upcoming events, overdue results and unknown schedules have distinct states.
   A browser clock updates date status even between static deployments. Dates
   are explicitly UTC; the feed is published snapshots, not live timing.
3. **The learned skill target repeats an input.** F2, F3, Formula E, NASCAR and
   IndyCar set `_target = roll_mean`, while `roll_mean_finish` is an input.
   Holding out drivers tests reconstruction of that statistic, not next-race
   prediction. This is not a future-result leak, but it is not validation of the
   claimed predictive task. A shared chronological research candidate now learns
   the *next* weekend's observed mean finish. F2/F3 adapters recompute features
   before each label round, omit current-cutoff Elo, exclude synthetic results,
   weight recent rounds, and hold out the last prior weekend to choose a blend
   with historical mean. It is opt-in through `F2_USE_TEMPORAL_SKILL=1` or
   `F3_USE_TEMPORAL_SKILL=1`; production defaults remain unchanged pending evidence.
4. **Promotion could overstate its sample and ignore a perfect-score regression.**
   The minimum sample now applies after taking the trailing window. Invalid,
   negative and non-finite errors do not count as evidence. A candidate that
   misses a production-perfect round triggers the regression guard. Promotion
   also requires a positive lower bound on the deterministic paired-round 95%
   bootstrap improvement interval, in addition to the existing effect-size and
   per-round checks. This aligns the decision with the evidence panel's uncertainty
   principle. The interval remains a small-sample heuristic, not proof of future gains.
5. **Refitting calibration retained old markets and strata.** Reusing an instance
   on a smaller historical window could carry a model fitted on later data into
   an earlier replay. Both calibrators now replace prior fitted state. Fractional
   observations are rejected instead of being silently truncated to zero or one.

## Reproduce the candidate experiment

Install the shared packages and F2/F3 projects as editable packages, or use:

```bash
PYTHONPATH=packages/motorsport-core/src:packages/motorsport-data/src:projects/f2-predictions/src:projects/f3-predictions/src \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  scripts/benchmark_temporal_skill.py --output docs/research/temporal-skill-benchmark.json
```

This is a retrospective walk-forward comparison of the **skill signal**, not a
live test or a complete race simulation A/B test. Every evaluated round is held
out from the feature history, fitting and blend selection used to predict it.
The committed report includes every scored round, baseline error, candidate
error, validation cutoff, confidence interval and gate decision. Historical
published forecasts are not regenerated or overwritten by this experiment.

## Initial experiment result

The committed snapshot supports only three eligible held-out F2 weekends and
two F3 weekends after reserving historical training and validation events. Both
candidates remain on **hold** under the five-round minimum. Small changes in
mean error at this sample size are not an established improvement. The report
contains the exact scores and intervals:

| Skill signal | Held-out weekends | Existing MAE | Candidate MAE | Decision |
| --- | ---: | ---: | ---: | --- |
| F2 | 3 | 3.7509 | 4.2650 | Hold; candidate is worse on this sample |
| F3 | 2 | 5.3734 | 5.3338 | Hold; too little evidence |

These errors describe the next weekend's average finish, not win probabilities.
The negative F2 result is a reason to keep the production model unchanged. F2/F3 XGBoost training is also limited
to one thread, matching the other series and preventing oversubscription on
small CI runners.

## Next model priorities

- Evaluate the candidate through full race simulation and each probability
  market on multiple historical seasons before considering default activation.
  F2/F3 currently offer few real completed rounds for this comparison.
- Port the chronological target design to FE/NASCAR/IndyCar with their own
  track, era and DNF features, rather than equating different series' labels.
- Evaluate calibration out of time and at race level, preserving pre-race
  snapshots separately from forecasts regenerated after results become known.
- Compare against qualifying order, recent form and standings on identical
  fields and cutoffs; published evidence already shows that several models
  have no demonstrated advantage over their strongest simple baseline.
- Resolve calendar/result ingestion gaps before marketing the feed as live.
  Endurance exports without dated schedules cannot populate an upcoming-race
  calendar reliably. The new adapter deliberately leaves dates unknown.

A single universal model is not justified by the current evidence. Shared
training/evaluation infrastructure with sport-specific targets is the practical
next step; cross-series transfer needs an out-of-time benchmark first.

## Design and deployment

The new home preserves the existing brand, typography, ambient preference and
series dashboards. The critical calendar is ordinary rendered content, so it
is usable without scroll-triggered animations. Keyboard buttons have pressed
states; search is labelled; reduced motion is respected; the detail panel stacks
below the scrollable race list on mobile. Favourite series are local to the
browser and do not require an account. The site remains a Next.js static export
for the existing GitHub Pages assembly.

Method references: [scikit-learn temporal cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split)
and [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports).

## Verification

- Hub: five Jest suites passed (66 tests, eight pre-existing skips); the final
  F1 completion-format regression brought the feed suite to seven passing tests.
- Production static export: TypeScript passed and all 21 pages generated.
- Browser: real Chromium checks passed for search, series filtering, saved
  following after reload, market switching, missing-result handling, navigation,
  and mobile overflow; no console or hydration errors. Desktop and mobile
  screenshots were reviewed. Reproduce with `cd website && node scripts/verify-race-centre.mjs`.
- Shared core/data and the complete F2/F3 suites: 517 tests passed.
- Python lint and shared UI synchronization checks passed.

