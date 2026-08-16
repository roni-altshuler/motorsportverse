# RaceIQ IMSA — IMSA WeatherTech SportsCar Championship

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
| Championship | IMSA WeatherTech SportsCar Championship |
| Category | endurance |
| Scoring unit | **car entry** |
| Classes racing together | GTP, LMP2, GTD PRO, GTD |
| Results source (not yet wired) | [the official IMSA results pages](https://www.imsa.com/) |

## What has to be decided first

These are not implementation details — each one changes the schema, the model,
or the meaning of a published number, and each is cheaper to settle now than to
reverse after a season of ratings has been fitted on the wrong assumption.

1. Multi-class, like WEC: several classes race simultaneously and an overall order mixes them. Everything in the WEC project's notes about per-class orders and per-class baselines applies here unchanged.

2. The calendar mixes sprint races with 6-, 10- and 24-hour endurance rounds, and the endurance rounds carry a separate points structure (the Michelin Endurance Cup). Two scoring systems run over one calendar.

3. Entry lists change materially between rounds — several classes have part-season entries — so a rating built on a stable roster assumption will be fitted on a roster that does not exist.

4. Driver line-ups per car change between endurance and sprint rounds, so car-level form and driver-level form diverge over a season.

## Where this diverges from the golden template

`projects/f3-predictions` is the canonical clone source, and it assumes a spec
series with one class, a fixed roster and two races per weekend. Not all of that
holds here.

- IMSA and WEC share a class structure but not a rulebook or a Balance of Performance process. Sharing a scraper between them is plausible; sharing a fitted model is not, and no number should cross between them.

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
cd projects/imsa-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

```python
from imsa_predictions.datasource import IMSADataSource
from imsa_predictions.predict import IMSAPredictor

source, predictor = IMSADataSource(), IMSAPredictor()
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
