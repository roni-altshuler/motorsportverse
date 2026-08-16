# RaceIQ Le Mans — 24 Hours of Le Mans

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
| Championship | 24 Hours of Le Mans |
| Category | endurance |
| Scoring unit | **car entry** |
| Classes racing together | HYPERCAR, LMP2, LMGT3 |
| Results source (not yet wired) | [the official 24 Hours of Le Mans results pages](https://www.24h-lemans.com/) |

## What has to be decided first

These are not implementation details — each one changes the schema, the model,
or the meaning of a published number, and each is cheaper to settle now than to
reverse after a season of ratings has been fitted on the wrong assumption.

1. **This project overlaps `wec-predictions` and the overlap must be resolved before either is built.** Le Mans is a round OF the World Endurance Championship. Two projects ingesting the same event will publish two different numbers for it, and nothing in the repo would detect the disagreement. Either this becomes a Le-Mans-specific VIEW over the WEC project's data, or WEC excludes the round explicitly.

2. It is ONE EVENT PER YEAR. Every walk-forward convention in this repo assumes multiple rounds within a season; here a season is a single observation, so the unit of evaluation has to be the year and the sample grows by one per year.

3. With roughly one usable observation per season, the calibration gate should be expected to stay closed for a very long time. That is the correct outcome, not a bug to engineer around.

4. The entry list is invitational and much larger than a WEC round, so grid size, class composition and retirement rates all differ from the championship rounds around it.

## Where this diverges from the golden template

`projects/f3-predictions` is the canonical clone source, and it assumes a spec
series with one class, a fixed roster and two races per weekend. Not all of that
holds here.

- Do not carry any WEC-fitted number into this project or the reverse until the overlap above is resolved. Two projects quietly disagreeing about one race is worse than either being absent.

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
cd projects/lemans-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

```python
from lemans_predictions.datasource import LeMansDataSource
from lemans_predictions.predict import LeMansPredictor

source, predictor = LeMansDataSource(), LeMansPredictor()
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
