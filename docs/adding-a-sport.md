# Adding a sport

This walks through creating a new prediction project end-to-end. F2 is the
worked example already in the repo (`projects/f2-predictions/`).

## 1. Scaffold

```bash
python scripts/new_project.py nascar-predictions \
  --sport "NASCAR" --category stock \
  --summary "Oval and road-course forecasts for the NASCAR Cup Series." \
  --accent "#FFD659" --added 2026-06-15
python scripts/build_registry.py   # validate + rebuild the catalog index
```

This creates `projects/nascar-predictions/` from the template and a
`concept`-maturity registry entry.

## 2. Implement the DataSource

Edit `src/<pkg>/datasource.py`. Return the canonical schema objects from
`motorsport_data.schema`:

```python
from motorsport_data.schema import Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

class NascarDataSource(DataSource):
    sport = "NASCAR"

    def season(self, year): ...      # calendar + roster
    def round(self, year, round): ...
    def results(self, year, round):  # [] until the round has run (leakage-safe)
        ...
```

For open-wheel series with an Ergast-compatible feed, reuse
`motorsport_data.sources.jolpica.JolpicaClient` instead of writing one.

## 3. Implement the Predictor

Edit `src/<pkg>/predict.py`. Supply features + a fit; reuse the core for
everything probabilistic:

```python
from motorsport_core import calibration, registry
from motorsport_core.interfaces import Predictor, RoundForecast

class NascarPredictor(Predictor):
    def fit(self, source, season, upto_round): ...   # train on rounds < upto_round
    def predict(self, source, season, round):
        probs = calibration.plackett_luce_probabilities(strengths)
        return RoundForecast(..., probabilities=probs)
```

Keep training **leakage-safe**: only use rounds strictly before the one you
predict (`motorsport_core.leakage.assert_prior_only`).

## 4. Wire continuous learning (optional but recommended)

- Persist models with `motorsport_core.registry.ModelRegistry`.
- Track health with `motorsport_core.drift` and gate releases with
  `motorsport_core.promotion`.
- Score with `motorsport_core.eval.score_round` against `HistoryStore` pairs.

## 5. Ship a website

Copy `website/src/components/ui` + `magicui` + `styles/tokens.css`, re-theme the
accent, point the data layer at your project's JSON output, and deploy the static
export. Reuse `.github/workflows/deploy-website.yml`.

## 6. Promote maturity

Update the project's `maturity` in `registry/projects/<slug>.json` as it
progresses (`concept → in-development → experimental → production`) and re-run
`build_registry.py`. See [GOVERNANCE.md](../GOVERNANCE.md) for the criteria.
