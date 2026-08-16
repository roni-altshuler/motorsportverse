# RaceIQ WEC — FIA World Endurance Championship

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
| Championship | FIA World Endurance Championship |
| Category | endurance |
| Scoring unit | **car entry** |
| Classes racing together | HYPERCAR, LMP2, LMGT3 |
| Results source (not yet wired) | [the official FIA WEC results pages](https://www.fiawec.com/) |

## What has to be decided first

These are not implementation details — each one changes the schema, the model,
or the meaning of a published number, and each is cheaper to settle now than to
reverse after a season of ratings has been fitted on the wrong assumption.

1. The scoring unit is a CAR, not a person. Two or three drivers share an entry and a driver can score in a car they did not finish in. The core `Competitor` dataclass models one competing entity, so the entry number is the competitor code and the crew is metadata — decide this before any modelling, because reversing it later invalidates every rating.

2. Races are MULTI-CLASS and run simultaneously. An overall finishing position mixes classes with completely different pace, so a single ranked order over the whole field is not the quantity anyone wants. Each class needs its own order, its own baselines and its own metrics.

3. Race length varies from 6 hours to 24. Retirement risk is not comparable across a 6-hour Imola and Le Mans, so a single DNF hazard fitted over all rounds would be wrong in both directions.

4. Balance of Performance is adjusted between events. Form carries across rounds far less reliably than in a spec series, which is exactly the assumption the F3 golden template is built on.

## Where this diverges from the golden template

`projects/f3-predictions` is the canonical clone source, and it assumes a spec
series with one class, a fixed roster and two races per weekend. Not all of that
holds here.

- Do NOT port F3's grid-order baseline unchanged: an endurance grid is set by a class-segregated qualifying and the overall order it implies is not a meaningful prediction.
- Do NOT reuse NASCAR's DNF-composition model without refitting. Its hazard is fitted on 500-mile ovals; a 24-hour race is a different distribution with a different shape, not the same one scaled up.

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
cd projects/wec-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

```python
from wec_predictions.datasource import WECDataSource
from wec_predictions.predict import WECPredictor

source, predictor = WECDataSource(), WECPredictor()
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
