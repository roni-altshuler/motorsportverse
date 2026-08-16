# Evidence policy

The standing rules for any accuracy claim made by any project in this repository.
[GOVERNANCE.md](../GOVERNANCE.md) says when a project may call itself production;
this says what it has to be able to show. [DESIGN.md](../DESIGN.md) §8 covers how
these rules change what the UI renders.

Read this before touching a model, an evaluation script, or an accuracy page.

---

## The six standing rules

### 1. The baseline is the benchmark

An accuracy number with no baseline is a number about the calendar, not about the
model. A grid that barely shuffles produces a flattering position error; a wet
race produces a terrible one. Neither says anything about whether the model
works.

Every project therefore publishes, alongside its own metrics, at least:

- **last-race order** — predict this round's finish as the previous round's
  finish. `motorsport_core.eval.last_order_baseline`.
- **grid order** — predict the finish as the starting grid, where the series has
  one that is known pre-race.

A claim is stated as *model versus a named baseline over N named rounds*, or it is
not stated.

### 2. Baselines are never deleted

They stay live as yardsticks even — especially — when the model beats them
comfortably. Deleting a baseline because it has been beaten is how a project
loses the ability to notice a regression. A model that cannot beat its baselines
does not serve; the honest response is to say so on the accuracy page, not to
remove the comparison.

### 3. Calibration gates the product

`calibration_summary.json.applied` stays **false** until enough real rounds have
accrued for the calibrator to have been fitted on reality. While it is false:

- the site says the probabilities are uncalibrated;
- no downstream surface may present them as a confidence level;
- **calibration is never claimed on synthetic or backfilled data.**

Displayed confidence never exceeds measured confidence.

### 4. A backtest is a backtest, forever

Three kinds of number live in this repo and they are never merged:

| | What it is | How it is labelled |
|---|---|---|
| **Backtest** | A completed season replayed with a model fitted only on earlier rounds | `--warning` colour, the word "backtest", everywhere it appears |
| **Forward-eval** | A prediction that was published *before* the round, scored after | the headline record |
| **Live** | The record accumulated since the site went up | reported at whatever `n` it has reached |

A retrodiction is leakage-safe and still not the same thing as a published call,
because **nobody read it before the lights went out.** A reconstructed forecast
must never blur into "published in advance".

The corollary: a project's first season has no forward record and should say so
rather than showing a backtest number in the slot where a live record goes.

### 5. A regression blocks promotion

`promotion_decision` compares a candidate against the served model on the rounds
they share and writes its verdict to `promotion_status.json`. A candidate that
loses does not ship, and the verdict is published rather than kept in a log.

There is no "record the regression and ship anyway". If the candidate is right
for a reason the metric does not capture, fix the metric first.

### 6. No fabricated data

Sparse coverage stays genuinely missing. Never impute a plausible value, never
placeholder a provider field, never fill a gap so a chart looks complete. A
missing round renders as missing.

This extends to the UI: **do not port a chart to a series whose export does not
genuinely supply its inputs.**

---

## The rule that catches the subtle failures

> **When a result looks too good, suspect the harness first.**

A model with no market features cannot out-predict a betting market. A model with
no weather features cannot beat a human on a wet race. A backtest that beats the
forward record on the same rounds is reading something it should not.

Every such result in this repo's history has been a bug announcing itself, and
each one produced a permanent guard:

- **Leakage at aggregation boundaries.** Multi-round aggregation must call
  `motorsport_core.leakage.assert_prior_only(...)`. A rolling feature computed
  over a window that includes the round being predicted looks entirely normal in
  the output.
- **Wrong-event data.** A live source that returns a *different* round's payload
  produces a well-formed, plausible, completely wrong prediction. Every source
  verifies round/date/venue/race-id against the config calendar before writing a
  snapshot, and every project has a fixture-based
  `tests/test_wrong_event_guards.py`. This exists because it happened: one
  race's grid was published as another round's prediction.
- **Train/serve skew.** A feature the training path populates and the serving
  path cannot silently falls back to the intercept. Compare **variance**, not
  names — the sibling soccer project's version of this bug had matching names
  and differing values.
- **Unordered streams.** Elo over rows that are not in chronological order reads
  the future, and the output looks entirely normal.

---

## What each project must publish

Under `website/public/data/`, produced solely by that project's `export.py`:

| Artifact | Carries |
|---|---|
| `forward_eval/round_NN.json` | per-round metrics, per-market Brier/log-loss, **and the baselines block** |
| `forward_eval/season.json` | the walk-forward roll-up, model and baseline side by side |
| `historical_backtest/` | the replay, labelled a backtest, with reliability plots |
| `calibration_summary.json` | `applied`, the training round count, and the honest `dataLimitation` string |
| `model_health.json` | feature and output drift, warnings and alarms |
| `promotion_status.json` | the candidate-vs-production verdict |

`motorsport_core.evidence.build_evidence()` reads the first two and produces the
single `EvidenceBlock` every site's `EvidencePanel` renders, so the comparison is
computed once in Python rather than re-derived in six TypeScript codebases.

`scripts/validate_published_data.py` checks the whole tree and exits non-zero on
any violation. It runs in CI and it is the fastest way to find out that an export
change quietly broke a downstream contract.

---

## Metrics are not comparable across series, ever

A Brier score over a 20-car F1 grid and a Brier score over a 40-car NASCAR field
are different numbers about different things. A rally scored on stages and a
sprint race scored on classified finishers are not on one scale.

**Never put two series' metrics in one table**, and never carry a conclusion from
one series to another — the sibling soccer and NBA projects have five measured
conclusions that invert between them, and motorsport is no kinder. Ovals and road
courses do not even agree within IndyCar, which is why that project runs dual
form.

What *is* comparable is a series against **its own** baselines, over time. That is
what every accuracy page shows.
