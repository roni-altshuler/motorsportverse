# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MotorsportVerse is a scverse-style monorepo: a project catalog plus shared ML/data
infrastructure for motorsport prediction. The **F1 flagship now lives IN this repo**
at `projects/f1-predictions/` (merged in from its former standalone repo, with full
git history) and is the reference implementation. It keeps its own toolchain, ruff
config, tests, and CLAUDE.md — treat it as a self-contained project; prefer reusing
`motorsport-core`/`motorsport-data` over duplicating, but F1's internals are its own.
Reusable code was lifted into two pip packages; each sport is a thin project on top.

```
packages/motorsport-core    shared ML: calibration (Plackett-Luce), championship MC,
                            standings, elo, conformal, eval, drift, promotion, registry, leakage
packages/motorsport-data    canonical pydantic schema, DataSource ABC, DuckDB HistoryStore,
                            shared FIA feeder-series scraper (sources/fia_feeder.py)
projects/f1-predictions     flagship & reference implementation (own pipeline + Next.js site)
projects/f2-predictions     first sport on the core (backend + its own Next.js site)
projects/f3-predictions     third series at F2 parity (real 2026 season; gold-themed site)
projects/<8 more>           scaffolded series (in-development): DataSource+Predictor stubs
website/                    ecosystem hub: landing + project catalog (Next.js)
registry/projects/*.json    the catalog — source of truth for which sports exist
scripts/                    build_registry*.{py,mjs} (validate+emit catalog), new_project.py
```

F1's CI, race-weekend cron, and history backfill were relocated to the monorepo
root as `.github/workflows/f1-*.yml` (GitHub only runs root workflows); they run
scoped to `projects/f1-predictions/` via `working-directory` + `PYTHONPATH`. The
unified `deploy-website.yml` builds hub + F1 + F2 into one Pages artifact.

## Environment & commands

There is no top-level Python package; install workspace members editable. The repo
uses **`uv`** (system venv is broken — always create one):

```bash
uv venv .venv && unset VIRTUAL_ENV
uv pip install --python .venv/bin/python -e "packages/motorsport-core[dev]" -e "packages/motorsport-data[dev]" scikit-learn xgboost requests pytest
```

The F2 project does NOT install cleanly via uv workspace (missing `tool.uv.sources`);
run its tests by adding `src/` to the path instead of installing it:

```bash
# Packages
PYTHONPATH=packages/motorsport-core/src  .venv/bin/python -m pytest packages/motorsport-core -q
PYTHONPATH=packages/motorsport-data/src  .venv/bin/python -m pytest packages/motorsport-data -q
# F2/F3 (run from the project dir; src layout — same pattern for both)
cd projects/f2-predictions && PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/test_model_f2.py -q     # single file
# Lint (what CI runs)
.venv/bin/ruff check packages projects scripts
```

Websites (both are Next.js 16, Tailwind v4, **static export** `output: "export"`):

```bash
cd website && npm run build                 # prebuild regenerates public/data/registry.json, then next build → out/
cd projects/f2-predictions/website && npm run build
node scripts/shoot.mjs [/tmp/out]           # Playwright screenshot harness (per site) — run after build
```

CI is `.github/workflows/ci.yml` (ruff + pytest on the two packages and f2, registry
validation, hub website build — it intentionally does NOT lint/test F1, which has its
own `f1-ci.yml`). `deploy-website.yml` regenerates F2 data and ships hub + F1 + F2 to
GitHub Pages under `/<repo>/`, `/<repo>/projects/f1/`, and `/<repo>/projects/f2/`. The
relocated F1 automation is `f1-ci.yml`, `f1-update-predictions.yml` (race-weekend
cron), and `f1-backfill-history.yml`.

## Architecture that spans files

**The reuse contract.** A sport supplies two things and inherits everything numerically
heavy: a `DataSource` (`motorsport_data.sources.base`) for calendar/results, and a
`Predictor` (`motorsport_core.interfaces`). The pipeline routes a per-driver pace/skill
score through `calibration.plackett_luce_probabilities` / `sample_finishing_orders` and
`championship.project_championship`. **Leakage discipline is enforced at boundaries**:
any multi-round aggregation must call `motorsport_core.leakage.assert_prior_only(...)`
with `current_round` and use only rounds strictly before it.

**The F2 model (`projects/f2-predictions/src/f2_predictions/model.py`)** is deliberately
*not* the F1 quali-time ensemble — F2 is a spec series, so driver skill dominates. It
blends Elo (rookie-pooled) + finishing history + an optional gradient-boosted signal
(`ml_skill.py`, GBR+XGB, flag `USE_ML_SKILL`) + optional Bayesian prior, then routes the
skill through two race-type heads: a **merit feature race** and a **reverse-grid sprint**
(top-N of the feature grid reversed + a grid penalty). All optional signals degrade to
`None`/GBR-only silently when deps are missing — `xgboost` is optional (CI installs it
for the full ensemble; without it `ml_skill` falls back to GBR alone, since scikit-learn
ships via `motorsport-core`).

**The FIA feeder scraper is shared.** fiaformula2.com and fiaformula3.com run the
same CMS, so the regex parser/calendar/entry-list machinery lives in
`motorsport_data.sources.fia_feeder.FiaFeederSource`; `FiaF2Source`/`FiaF3Source`
are thin bindings that inject base URL + season anchor raceids + session headings.
F2's fixture-HTML tests are the parsing contract — never change the regexes
without running them. F3-specific sporting facts (9-round 2026 calendar after the
Sakhir cancellation, 30-car grid, reverse-top-12 sprint, sprint points 10..1)
were verified against the live site and are encoded in F3's `config.py`.

**F2 data source seam.** `datasource.py` picks `CompositeF2Source` when
`F2_USE_LIVE_RESULTS=1` (real fiaformula2.com scrape via `sources/fia_f2_source.py`, with
synthetic fallback + provenance), else the deterministic `SyntheticF2Source`. The
synthetic generator (`config._TRUTH_PACE`) keeps the pipeline runnable/testable offline;
tests run on it. The live scraper needs a season anchor raceid in
`config.FIA_F2_SEASON_ANCHORS` and is reliable for completed seasons (e.g. 2024) but
partial/flaky for an in-progress season. The site currently runs the **real 2026 grid +
calendar** (from the feed) with **model-generated standings** over that real roster — i.e.
real identities, forecast results.

**The website data contract.** `export.py` is the single producer of the F2 site's JSON
(`website/public/data/`: `f2.json`, `rounds/round_NN.json`, `probabilities/round_NN.json`,
`forward_eval/`, `model_health.json`, `calibration_summary.json`). It intentionally
mirrors the F1 flagship's fan-out shape so the F2 site reuses F1 components 1:1. When you
change Python output, update `src/types/f2.ts` and the pydantic mirror in
`tests/test_website_data_schema.py` in the same change (CI gates it). Regenerate with
`PYTHONPATH=src .../python -m f2_predictions.export`.

**Calibration is honestly gated.** `calibration_summary.json.applied` stays `false` (with
a site banner) until enough *real* rounds are backfilled; never claim calibration on
synthetic data.

## Frontend specifics

- Both sites are static exports — client-only libs (recharts/visx/gsap/lenis, WebGL,
  IntersectionObserver code) must live in `"use client"` components and never break
  `next build`. The F2 site's `.npmrc` pins `legacy-peer-deps=true` so `@visx/*` (peers
  React 16–18) installs on React 19 — do not delete it.
- **Never import the fs-based data loader (`lib/f2data.ts`, `lib/registry.ts`) from a
  client component** — it pulls `node:fs` into the browser bundle and the build fails.
  Pure helpers used client-side live in fs-free modules (`lib/teams.ts`).
- Scroll-reveal must never leave content permanently invisible (SSR/no-JS/headless): use
  the failsafe `useReveal` hook / `animate`-on-mount rather than bare framer `whileInView`.
- The F2 site mirrors the F1 flagship's design system, themed F2 electric-blue
  (`--accent: #1E9BD7`). Driver headshots use `DriverPortrait` (resolves
  `/headshots/<CODE>.webp`, falls back to a conic-gradient initials avatar). Circuit SVG
  track maps reuse F1's fastest-lap geometry, shipped as `public/data/circuits.json`
  keyed by venue.
- **Tech-stack scrub:** user-facing pages must not name implementation details
  (Plackett-Luce, Elo, XGBoost, Monte Carlo, isotonic, etc.) — describe what the model
  says, not how. Methodology belongs in READMEs.
- **Race-art discipline:** calendar/circuit imagery must be aerial circuit photography
  (`lib/raceArt.ts`, curl-verified Wikimedia SkySat) — never SVG diagrams, logos, or
  country landscapes.

## Registry

`registry/projects/<slug>.json` is the catalog source of truth; `scripts/build_registry.py`
(and the `prebuild` node variant) validate against `registry/schema/` and emit
`website/public/data/registry.json` consumed at build time. Add a sport via
`scripts/new_project.py` (see `docs/adding-a-sport.md`). Concept entries have empty
`repo`/`website` and the UI must hide their demo/source buttons rather than render dead links.
