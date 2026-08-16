# Adding a sport

This walks through creating a new prediction project end-to-end. F2 is the
worked example already in the repo (`projects/f2-predictions/`); F3
(`projects/f3-predictions/`) shows how fast the second pass goes when the
data platform is shared — its scraper is a ~30-line binding of
`motorsport_data.sources.fia_feeder.FiaFeederSource`.

Five series (WEC, MotoGP, WRC, IMSA, Le Mans) are already scaffolded under
`projects/` with curated registry entries at `in-development` — for those, skip
step 1 and start at step 2. **Read that project's README first:** each one
records the format-specific decisions that have to be settled before an ingester
can be written, and every one of them changes the schema or the meaning of a
published number. They are much cheaper to settle now than to reverse after a
season of ratings has been fitted on the wrong assumption.

## 1. Scaffold

```bash
python scripts/new_project.py supercars-predictions \
  --sport "Supercars" --category stock \
  --summary "Forecasts for the Repco Supercars Championship." \
  --accent "#FFD659" --added 2026-07-02
python scripts/build_registry.py   # validate + rebuild the catalog index
```

If the catalog already carries a curated entry for the slug, scaffold the
project tree only — the script refuses to overwrite curated entries:

```bash
python scripts/new_project.py <slug> --sport ... --summary ... --skip-registry
```

This creates `projects/nascar-predictions/` from the template and a
`concept`-maturity registry entry.

## 2. Implement the DataSource

Edit `src/<pkg>/datasource.py`. Return the canonical schema objects from
`motorsport_data.schema`:

**There are two ABCs called `DataSource` and they are not the same.**
`motorsport_data.sources.base.DataSource` is the *ingestion* contract
(`season` / `round` / `results`, returning canonical schema objects);
`motorsport_core.interfaces.DataSource` is the contract a `Predictor` consumes
(`calendar` / `grid` / `results`). A scaffold that declares the core `Predictor`
while calling the data ABC's methods cannot be wired up, and that mistake sat in
the project template for months. The five scaffolded projects now implement the
**core** contract; follow them.

```python
from motorsport_core.interfaces import Competitor, DataSource, GridEntry, Venue

class NascarDataSource(DataSource):
    sport = "NASCAR"

    def calendar(self, season): ...          # ordered venues, index 0 == round 1
    def grid(self, season, round): ...       # entry list + pre-event state
    def results(self, season, round):        # {} until the round has run
        ...
```

For open-wheel series with an Ergast-compatible feed, reuse
`motorsport_data.sources.jolpica.JolpicaClient` instead of writing one.

**Snapshot-first.** Every implemented series reads a committed snapshot under
`data/official_<season>.json` as its offline source of truth, so a downstream
build never touches the network and a flaky live source no-ops the run instead
of publishing a degraded one. Copy `sources/snapshot.py` from any scaffolded
project: `load()` returns `None` for "never ingested", `require()` fails loudly
and names the missing file.

**Wrong-event guards are not optional.** Every live source verifies the returned
payload's identity — round, date, venue, race id — against the config calendar
*before* any snapshot write, with a fixture-based `tests/test_wrong_event_guards.py`
beside it. This exists because one race's grid was once published as another
round's prediction, and the output looked entirely normal.

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
predict, and **assert it at the boundary** with
`motorsport_core.leakage.assert_prior_only` rather than trusting the loop bound
you just wrote. A rolling feature computed over a window that includes the round
being predicted produces output that looks entirely normal.

**Publish the probabilities coherently.** After calibration, call
`motorsport_core.calibration.renormalize_market_struct(struct, digits=4)`.
Per-competitor isotonic calibration does not preserve the simplex, and the sites
render `probability` straight as a percentage — five series published win
markets summing to as much as 2.00 because this step was missing. Round *after*
the water-fill, never before.

**Publish baselines beside every metric.** `motorsport_core.eval.last_order_baseline`
gives the last-race baseline; add a grid-order baseline wherever the series has a
grid known pre-race. A metric with no baseline is a number about the calendar,
not about the model, and `validate_published_data.py` fails a scored round that
has none. See [EVIDENCE.md](EVIDENCE.md).

## 4. Wire continuous learning (optional but recommended)

- Persist models with `motorsport_core.registry.ModelRegistry`.
- Track health with `motorsport_core.drift` and gate releases with
  `motorsport_core.promotion`.
- Score with `motorsport_core.eval.score_round` against `HistoryStore` pairs.

## 5. Ship a website

Copy `website/src/components/{ui,magicui}` + `styles/tokens.css`, re-theme the
accent, point the data layer at your project's JSON output, and deploy the static
export. Reuse `.github/workflows/deploy-website.yml`.

In the **same change**, so the site is gated from day one:

- Add the site to `TARGETS` in `scripts/sync_shared_ui.mjs`, then run
  `node scripts/sync_shared_ui.mjs` and `--check`. This also brings the shared
  test suite under `src/__tests__/shared/`.
- Copy the site's `jest.config.js` / `jest.setup.js` and the test devDependencies
  from any existing site. `@testing-library/dom` must be a **direct**
  devDependency — `.npmrc` pins `legacy-peer-deps=true`, so npm will not install
  it as a peer.
- Add `error.tsx`, `not-found.tsx`, `global-error.tsx`, `manifest.ts`, `robots.ts`
  and `sitemap.ts`.
- Render `<EvidencePanel evidence={getEvidence()} />` on the accuracy page. It is
  deliberately not a tab, and it sits below the numbers it justifies.
- Add the site to the `websites` matrix in `.github/workflows/ci.yml`.
- Keep the accent theming in `styles/tokens.css` only. A light accent needs a
  near-black `--accent-ink`; a deep accent needs a *brightening* hover. See
  [DESIGN.md](../DESIGN.md) §1.2.

## 6. Check the corpus, not just the files

```bash
python scripts/validate_published_data.py <slug>
```

Schema tests prove each file is well-formed; this asks whether the published
corpus is right — contiguous rounds, dates that increase, probabilities that sum
to the field they describe, a baseline beside every scored round, an honest
calibration gate. Run it after any export change. It must pass with no `--allow`
flags.

## 7. Promote maturity

Update the project's `maturity` in `registry/projects/<slug>.json` as it
progresses (`concept → in-development → experimental → production`) and re-run
`build_registry.py`. See [GOVERNANCE.md](../GOVERNANCE.md) for the criteria.
