# RaceIQ WRC — FIA World Rally Championship

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
| Championship | FIA World Rally Championship |
| Category | rally |
| Scoring unit | **crew** |
| Classes racing together | Rally1, Rally2, Rally3 |
| Results source (not yet wired) | [the official WRC results pages](https://www.wrc.com/) |

## What has to be decided first

These are not implementation details — each one changes the schema, the model,
or the meaning of a published number, and each is cheaper to settle now than to
reverse after a season of ratings has been fitted on the wrong assumption.

1. A rally is not a race. Crews start at intervals and the classification is CUMULATIVE STAGE TIME over ~20 stages, so the natural prediction is a time distribution rather than a finishing order. Ranking is a consequence of the times, not the model's output.

2. Road position is a real, large, ORDERED disadvantage on gravel — the leader sweeps loose surface for those behind — and the running order is set by the previous leg's classification. A model that ignores it will systematically over-rate whoever led on day one.

3. The scoring unit is a CREW: a driver and a co-driver. Pairings change between seasons and occasionally mid-season.

4. Points come from more than the final classification — Super Sunday and the Power Stage award separately. A championship simulation that only models the rally result will drift from the real table.

## Where this diverges from the golden template

`projects/f3-predictions` is the canonical clone source, and it assumes a spec
series with one class, a fixed roster and two races per weekend. Not all of that
holds here.

- Stage-level data is the natural granularity, so `Result.position` alone loses most of the signal. Expect to extend the canonical schema rather than squeeze rallying into a per-round finishing order.
- The last stage is worth disproportionate points, so a leakage-safe backtest must respect stage order WITHIN a round, not only between rounds. `assert_prior_only` operates on rounds and is not sufficient here.

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
cd projects/wrc-predictions
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

```python
from wrc_predictions.datasource import WRCDataSource
from wrc_predictions.predict import WRCPredictor

source, predictor = WRCDataSource(), WRCPredictor()
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
