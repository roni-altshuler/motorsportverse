# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MotorsportVerse is a scverse-style monorepo: a project catalog plus shared ML/data
infrastructure for motorsport prediction. Reusable code lives in two pip packages;
each sport is a thin project on top. The **F1 flagship lives IN this repo** at
`projects/f1-predictions/` (own toolchain, ruff config, tests, CLAUDE.md — treat it
as self-contained). Six series are full products; the rest are scaffolded stubs.

```
packages/motorsport-core     shared ML: calibration (Plackett-Luce), championship MC,
                             standings, elo, conformal, eval, drift, promotion, leakage
packages/motorsport-data     canonical pydantic schema, DataSource ABC, DuckDB HistoryStore,
                             shared FIA feeder scraper (sources/fia_feeder.py) w/ wrong-event guards
projects/f1-predictions      flagship (flat src/ layout; post-quali overhaul: grid provenance,
                             self-correcting freeze, candidate model, honest baselines)
projects/f2-predictions      full product ("golden template" parity; reverse-top-10 sprint)
projects/f3-predictions      full product — THE GOLDEN TEMPLATE new series clone
projects/formula-e-predictions  full product, LIVE (pulselive API, doubleheaders, street/circuit strata)
projects/nascar-predictions  backend complete (cf.nascar.com, DNF-composition model, 2026 Chase
                             title MC + 2017-25 elimination format for backtests); website WIP
projects/indycar-predictions curated verified history 2012-2026 committed; snapshot-primary
                             pipeline WIP (no public API — committed data files are ground truth)
projects/<5 more>            scaffolded stubs (wec, motogp, wrc, imsa, lemans)
website/                     ecosystem hub: landing + registry-driven catalog (Next.js)
registry/projects/*.json     the catalog — source of truth for which sports exist + maturity
scripts/                     build_registry*.{py,mjs}, sync_shared_ui.mjs (drift gate), new_project.py
```

**Buildout status (2026-07-08):** the "complete the universe" effort is mid-flight on
branch `feat/universe-phase0-f3-f2-parity`. Merged to main + live: F1 overhaul
(winner-hit 77.8% w/ baselines), F2/F3 parity, Formula E (site + cron), NASCAR backend,
IndyCar curated history. WIP commits on the feature branch (labeled `wip(...)`, tests
partially failing by design): NASCAR website (~FE clone, retheme unfinished), IndyCar
pipeline (src written, tests partial). Remaining after those: NASCAR CI wiring +
registry (copy the Formula E recipe, commit `cfbbe0c`), IndyCar website + CI, docs
refresh. Session-resume details live in the user's Claude memory.

## Environment & commands

No top-level Python package; install workspace members editable. Use **`uv`** for the
venv (system venv is broken), but note **uv cannot editable-install the projects**
(missing `tool.uv.sources`) — use `PYTHONPATH=src` per project instead; plain `pip`
in CI handles them with `--no-deps`.

```bash
uv venv .venv && unset VIRTUAL_ENV
uv pip install --python .venv/bin/python -e "packages/motorsport-core[dev]" -e "packages/motorsport-data[dev]" scikit-learn xgboost requests numpy matplotlib duckdb pytest
```

```bash
# Packages
PYTHONPATH=packages/motorsport-core/src .venv/bin/python -m pytest packages/motorsport-core -q
PYTHONPATH=packages/motorsport-data/src .venv/bin/python -m pytest packages/motorsport-data -q
# Any project (same pattern: f2, f3, formula-e, nascar, indycar)
cd projects/f3-predictions && OMP_NUM_THREADS=1 PYTHONPATH=src ../../.venv/bin/python -m pytest -q
OMP_NUM_THREADS=1 PYTHONPATH=src ../../.venv/bin/python -m pytest tests/test_model_f3.py -q  # single file
# Pipelines run as modules from the project dir (export/refresh/forward_eval/
# historical_backtest/promotion_decision/season_rollover/backfill/race_weekend):
PYTHONPATH=src ../../.venv/bin/python -m f3_predictions.export
# Lint (what CI runs)
.venv/bin/ruff check packages projects scripts
```

**Gotcha:** always pin `OMP_NUM_THREADS=1` for anything importing xgboost — it hangs
in OpenMP spin-wait under CPU contention. matplotlib is needed by each project's
`historical_backtest` (reliability PNGs) but is not in CI's core installs; backtest
tests guard with `pytest.importorskip("matplotlib")` — keep that in new projects.

Websites (all Next.js 16, Tailwind v4, static export):

```bash
cd projects/<slug>-predictions/website && npm install && PAGES_BASE_PATH= npm run build
node scripts/shoot.mjs [/tmp/out]   # per-site Playwright screenshot harness, run after build
cd website && npm run build         # hub; prebuild regenerates public/data/registry.json
```

CI: `ci.yml` (packages + f2/f3/formula-e + stub loop + registry validation + shared-UI
drift check + hub build; F1 excluded — it has `f1-ci.yml`). `deploy-website.yml` builds
hub + F1 + F2 + F3 + Formula E into ONE Pages artifact under `/<repo>/projects/<slug>/`
— **adding a sport = add an install line, a "Generate <sport> data" step, a build block,
and an assemble `cp -r` there**, plus a `<slug>-update-predictions.yml` cron (copy an
existing one; each includes a freshness gate, season bootstrap/rollover --auto steps,
schema-gated commit, and a `committed`-gated deploy call).

## Architecture that spans files

**The reuse contract.** A sport supplies a `DataSource` (`motorsport_data.sources.base`)
and a `Predictor` (`motorsport_core.interfaces`); everything numerically heavy comes
from core (`calibration.plackett_luce_probabilities` / `sample_finishing_orders`,
`championship.project_championship`). **Leakage discipline is enforced at boundaries**:
multi-round aggregation must call `motorsport_core.leakage.assert_prior_only(...)`.

**The golden-template module set** (F3 is canonical; FE/NASCAR are the newest clones —
prefer them as reference for single-race series): `config / datasource / model /
ml_skill / position_head / pipeline / predict / export / refresh / race_weekend /
forward_eval / historical_backtest / drift_report / promotion_decision / backfill /
season_rollover / bootstrap_next_season` + `sources/{<live>_source,snapshot,synthetic,
composite}`. Every series follows the same conventions:

- **Committed snapshot is the offline source of truth** (`data/official_<season>.json`):
  downstream builds never touch the network; a flaky live source no-ops the run.
  IndyCar inverts fully — its committed `data/history_<year>.json` files ARE the data
  (verified per-season against official standings; see `data/CURATION_REPORT.md`).
- **Wrong-event guards everywhere**: every live source verifies the returned payload's
  identity (round/date/venue/race_id) against the config calendar before any snapshot
  write; fixture-based `test_wrong_event_guards.py` per project. Born from a real F1
  incident (wrong race's grid published as another round's prediction).
- **A/B gates**: optional model heads (e.g. `position_head`) ship behind env flags
  (`<SPORT>_USE_POSITION_HEAD`, default OFF); `promotion_decision` compares candidate
  vs production walk-forward and emits the verdict into `promotion_status.json`.
- **Multi-season**: `config` resolves the active season via env → `data/active_season.json`
  marker → literal default; `season_rollover --auto` archives finished seasons to
  `website/public/data/seasons/<year>/` and starts announced ones; the site's
  `SeasonProvider` + `seasons.json` drive the switcher with archived-season overlays.
- **Honest evaluation**: `forward_eval` publishes per-round markets (Brier/log-loss)
  plus **baselines** (last-race, grid-order); accuracy pages always show model-vs-baseline.
  Calibration is gated: `calibration_summary.json.applied` stays false until enough
  real rounds accrue — never claim calibration on synthetic data.

**F1 specifics** (post-overhaul): every published round records `gridProvenance`
(`real-quali-verified`/`estimated`/`stale`); `gp_weekend.needs_update` re-freezes
post-quali until a verified real-grid freeze exists (idempotent cron); wrong events
cannot reach verified status (`fetch_qualifying_data(expected_round=)`).
`models/candidate_model.py` (quali-gap seconds + per-circuit grid-trust priors from
`features/data/circuit_priors.json`) ships via `F1_CANDIDATE_MODEL=1` in the cron.
`src/regenerate_post_quali.py` replays completed rounds leakage-safely (old state
archived under `website/public/data/archive/pre-overhaul/`).

**NASCAR specifics**: DNF hazard is a first-class production component (sample DNFs
first, rank survivors); title odds route through `championship_playoffs.py`
(`PlayoffFormat` expresses both the 2026 Chase — top-16 on points, 10-race cumulative,
no eliminations, 55-pt win — and the 2017-25 elimination bracket for backtests). The
playoff panel is gated on `historical_backtest/playoffs.json:gate.pass`. Backfill floor
is 2018 (the 2017 cacher endpoint serves wrong-season data; a guard refuses it).

**The FIA feeder scraper is shared** (fiaformula2.com/fiaformula3.com run one CMS):
parser lives in `motorsport_data.sources.fia_feeder.FiaFeederSource`; F2/F3 sources are
thin bindings. F2's fixture-HTML tests are the parsing contract — never change the
regexes without running them.

**The website data contract.** Each project's `export.py` is the single producer of its
site's JSON (`website/public/data/`: `<slug>.json`, `rounds/`, `probabilities/`,
`forward_eval/`, `historical_backtest/`, `reliability_plots/`, `calibration_summary`,
`model_health`, `promotion_status`, `seasons.json`). Shapes mirror across sites so
components port 1:1. When you change Python output, update the site's TS types AND the
pydantic mirror in `tests/test_website_data_schema.py` in the same change (CI gates it).

## Frontend specifics

- All sites are static exports — client-only libs must live in `"use client"`
  components; never import fs-based data loaders (`lib/<slug>data.ts`, `lib/registry.ts`)
  from client components. `.npmrc` pins `legacy-peer-deps=true` — do not delete it.
- **Shared design system**: F1's `website/src/components/{ui,magicui}` is canonical;
  F2/F3/Formula E carry byte-identical copies enforced by `node scripts/sync_shared_ui.mjs
  --check` in CI — add each new site to its TARGETS in the same change that copies the
  site. Theming happens ONLY via each site's `styles/tokens.css` accent tokens
  (F1 `#E10600`, F2 `#1E9BD7`, F3 `#D9A441`, FE `#1E1AF0`, NASCAR `#FFD659` — light
  accents need near-black `--accent-ink`, deep accents need brightening hovers).
  Charts (`components/charts/`) are per-site adapted, deliberately NOT drift-gated.
- **Don't fake data**: port only charts whose inputs the sport's export genuinely
  supplies (no telemetry charts without telemetry). Scroll-reveal must never leave
  content permanently invisible (use the failsafe `useReveal` pattern).
- **Tech-stack scrub:** user-facing pages must not name implementation details
  (Plackett-Luce, Elo, XGBoost, Monte Carlo…) — describe what the model says, not how.
- **Race-art discipline:** calendar/circuit imagery must be aerial circuit photography
  (`lib/raceArt.ts`), every URL curl-verified — never SVG diagrams, logos, or country
  landscapes; fall back to the gradient card rather than a wrong image.

## Registry

`registry/projects/<slug>.json` is the catalog source of truth; `scripts/build_registry.py`
validates against `registry/schema/` and emits `website/public/data/registry.json`
(the hub's prebuild runs the node variant). Maturity path: in-development →
experimental (site live, snapshot pipeline running) → production (accuracy accrued on
real rounds). Concept entries have empty `repo`/`website`; the UI hides their buttons.
`docs/adding-a-sport.md` is the step-by-step runbook for promoting a stub to a product.
