# RaceIQ MotoGP — MotoGP

**Maturity: in-development.** The project tree, the shared-core seams and the
test suite are real. **No data feed is wired, so this series publishes nothing**
— see [what has to be decided first](#what-has-to-be-decided-first).

That distinction is the point. Every accessor here returns empty rather than a
plausible calendar or a plausible result, and there are tests asserting it. A
scaffold that returns convincing fake data is far more dangerous than one that
returns nothing, because the fake data reaches a chart.

## The series

| | |
|---|---|
| Championship | MotoGP |
| Category | motorcycle |
| Scoring unit | **rider** |
| Classes racing together | MotoGP, Moto2, Moto3 |
| Results source (not yet wired) | [the official MotoGP results pages](https://www.motogp.com/en/gp-results) |

## What has to be decided first

These are not implementation details — each one changes the schema, the model,
or the meaning of a published number, and each is cheaper to settle now than to
reverse after a season of ratings has been fitted on the wrong assumption.

1. A Grand Prix weekend has TWO scoring races — a Saturday sprint and the Sunday Grand Prix — sharing one qualifying result. That is the F2/F3 two-race shape, which is why the feeder template is the right clone source here rather than the single-race one.

2. The sprint grid is the SAME as the Grand Prix grid, unlike F2/F3 where the sprint grid is a partial reversal. Porting the feeder template's reverse-top-10 logic would produce a grid nobody lines up on.

3. Three classes run at each event. They share a calendar and nothing else — separate riders, separate machinery, separate ratings.

4. Crash-out rates are materially higher than in car racing and vary by circuit and conditions, so a finish-position model that ignores non-finishes will be confidently wrong on wet weekends.

## Where this diverges from the golden template

`projects/f3-predictions` is the canonical clone source, and it assumes a spec
series with one class, a fixed roster and two races per weekend. Not all of that
holds here.

- A rider's identity is stable across a season but machinery changes materially between manufacturers; the rider/constructor split that works for F1 needs re-checking before it is assumed here.

## What is already true

- `config.py` — series identity, the classes that race together, and the season
  resolution order every other project uses (env → marker → default).
- `sources/snapshot.py` — the committed-snapshot seam. `load()` returns `None`
  for "never ingested"; `require()` fails loudly and names the missing file and
  the source that would produce it.
- `datasource.py` — implements `motorsport_core.interfaces.DataSource`
  (`calendar` / `grid` / `results`), the contract a `Predictor` actually
  consumes. The previous scaffold declared the core `Predictor` while calling
  the `motorsport_data` DataSource's `season`/`round`/`results`: two different
  ABCs with the same name, so the seam could never have been wired as written.
- `predict.py` — a working prior-form predictor with the leakage assertion at
  the boundary. Simple on purpose: "can the shared core beat a trivial baseline
  for this sport" is the experiment that has to run before anything more
  elaborate is justified.
- `tests/` — contract conformance, the no-fabrication guarantees, and the
  leakage boundary. They run in CI today.

## Running it

```bash
cd projects/motogp-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

```python
from motogp_predictions.datasource import MotoGPDataSource
from motogp_predictions.predict import MotoGPPredictor

source, predictor = MotoGPDataSource(), MotoGPPredictor()
predictor.fit(source, 2026, upto_round=5)
forecast = predictor.predict(source, 2026, 5)
# forecast.predicted_order == {} — there is no snapshot, and that is honest.
```

## Promoting this to a product

[`docs/adding-a-sport.md`](../../docs/adding-a-sport.md) is the runbook and
[`GOVERNANCE.md`](../../GOVERNANCE.md) is the maturity ladder. In short: settle
the questions above, write the ingester and commit a snapshot, add the
golden-template module set (`model`, `pipeline`, `export`, `refresh`,
`forward_eval`, `historical_backtest`, `drift_report`, `promotion_decision`,
`season_rollover`), add `tests/test_wrong_event_guards.py`, then the website and
the cron. Do not skip the wrong-event guards — they exist because one race's
grid was once published as another round's prediction.
