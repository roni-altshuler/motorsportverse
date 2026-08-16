# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MotorsportVerse is a scverse-style monorepo: a project catalog plus shared ML/data
infrastructure for motorsport prediction. Reusable code lives in two pip packages;
each sport is a thin project on top. The **F1 flagship lives IN this repo** at
`projects/f1-predictions/` (own toolchain, ruff config, tests, CLAUDE.md — treat it
as self-contained). Six series are full products; the rest are scaffolded stubs.

```
packages/motorsport-core     shared ML: calibration (Plackett-Luce + post-calibration
                             market renormalisation), championship MC, standings, elo,
                             conformal, eval, evidence, integrity, drift, promotion, leakage
packages/motorsport-data     canonical pydantic schema, DataSource ABC, DuckDB HistoryStore,
                             shared FIA feeder scraper (sources/fia_feeder.py) w/ wrong-event guards
projects/f1-predictions      flagship (flat src/ layout; post-quali overhaul: grid provenance,
                             self-correcting freeze, candidate model, honest baselines)
projects/f2-predictions      full product ("golden template" parity; reverse-top-10 sprint)
projects/f3-predictions      full product — THE GOLDEN TEMPLATE new series clone
projects/formula-e-predictions  full product, LIVE (pulselive API, doubleheaders, street/circuit strata)
projects/nascar-predictions  full product (cf.nascar.com, DNF-composition model, 2026 Chase
                             title MC + 2017-25 elimination format for backtests)
projects/indycar-predictions full product — snapshot-primary (no public API: curated verified
                             history 2012-2026 IS the ground truth), dual oval/road-street form
projects/chrome-valley-racing  FANTASY fun project: simulated story league (stdlib-only sim,
                             bespoke site w/ in-browser race sim; NOT drift-gated, no cron)
projects/prism-cup-karting   FANTASY fun project: simulated kart league (same shape)
projects/<5 more>            scaffolded, CONTRACT-TESTED seams (wec, motogp, wrc, imsa,
                             lemans): real config/snapshot/datasource/predict + tests that
                             assert nothing is fabricated. No feed wired — they publish nothing.
website/                     ecosystem hub: landing + registry-driven catalog (Next.js)
registry/projects/*.json     the catalog — source of truth for which sports exist + maturity
scripts/                     build_registry*.{py,mjs}, sync_shared_ui.mjs (drift gate),
                             validate_published_data.py (corpus integrity), new_project.py
```

**The four docs that govern changes here.** Read the relevant one before editing:
[`DESIGN.md`](DESIGN.md) (the visual system, in getdesign.md format),
[`docs/EVIDENCE.md`](docs/EVIDENCE.md) (what an accuracy claim has to show),
[`GOVERNANCE.md`](GOVERNANCE.md) (the maturity ladder), and
[`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) (defects carried on purpose, each with
the gate waived for it — currently none).

**Buildout status (2026-07-10):** Phase 0 ("complete the universe") is DONE on branch
`feat/universe-phase0-f3-f2-parity`: F1 overhaul, F2/F3 parity, Formula E, NASCAR and
IndyCar are all full products (backend + website + CI/cron wiring + registry), six
sites ship in one Pages artifact. All seven test suites green; drift gate + registry
validated. All six implemented series are at **production** maturity (deployed site +
scheduled refresh + public forward-eval, per GOVERNANCE.md). The two FANTASY fun projects
(chrome-valley-racing, prism-cup-karting — Cars-movie- and kart-racer-inspired) are fully
simulated + interactive, registry category "fantasy", original IP-safe naming, fan-made
disclaimers; they regenerate deterministic seeded data at deploy time and carry no cron.

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
# Scaffolded series (stdlib+core only, no heavy deps):
cd projects/wec-predictions && PYTHONPATH=src ../../.venv/bin/python -m pytest -q
# Corpus integrity over EVERY project's published data — run after any export change
python scripts/validate_published_data.py            # -v for passing checks too
python scripts/validate_published_data.py f3 nascar  # a subset
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
npm test                            # Jest + Testing Library; every site has a suite
node scripts/shoot.mjs [/tmp/out]   # per-site Playwright screenshot harness, run after build
node ../../../scripts/sync_shared_ui.mjs --check   # shared component + test drift gate
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

**The golden-template module set** (F3 is canonical; NASCAR/IndyCar are the newest
clones — prefer them as reference for single-race series; IndyCar for snapshot-primary): `config / datasource / model /
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

**NASCAR does not beat grid order, and the site says so.** Measured over 19 paired
rounds of 2026: pre-qualifying mean position error **9.81 vs grid order's 9.03**,
improvement −0.78 with a 95% CI of [−1.29, −0.22] — entirely below zero. It *does* beat
the last-race baseline. This was masked until 2026-08 because the name-keyed baselines
were being attached to the `racePostQuali` block (8.91, a near-tie) instead of the `race`
block they actually score; `evidence._primary_race_type` now pins it. **Do not quote the
post-quali number against a pre-quali baseline** — a model that has seen the grid is not
competing with a baseline that is the grid. Grid order is a strong baseline in a series
where track position is this decisive, and losing to it is the honest current state.

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
`export.py` also publishes `evidence.json` (via `forward_eval`) — see below.

**Evidence is computed once, in Python.** `motorsport_core.evidence.build_evidence()`
reads the published `forward_eval/` tree and emits one `evidence.json` per project:
model vs each baseline, **paired on the rounds they both scored**, with a seeded
percentile bootstrap and a verdict of better/worse/inconclusive/insufficient. Every
site renders it through the shared `EvidencePanel`. Deriving the comparison in
TypeScript instead would put it in six codebases that drift independently, and a
component that recomputes a number is a second model nobody benchmarked. Below
`MIN_ROUNDS_FOR_CLAIM` (5) the verdict is `insufficient` however good the delta
looks, and a CI straddling zero is `inconclusive` rather than the sign of the point
estimate. **A losing comparison is published, in words** — there is no code path
that hides one.

**Integrity is checked at the CORPUS level, not per file.**
`python scripts/validate_published_data.py` runs `motorsport_core.integrity` over
every project's `website/public/data/`: contiguous rounds, dates that increase,
no future-dated completed round, no duplicate or placeholder competitors,
probabilities in [0,1] **and summing to their market's set size**, a baseline
beside every scored round after round 1, an honest calibration gate, a coherent
season manifest, recognised drift severities. **Run it after any export change.**
A project with nothing published is skipped, not failed. `--allow <check>` carries
a known defect and every allowance needs an entry in `docs/KNOWN_ISSUES.md`; the
flag lives in the CI invocation, never a config file, so a reader trips over it.

**The lesson that check was born from (2026-08).** Per-competitor isotonic
calibration does not preserve the simplex — a published win market summed to as
much as 2.00 across F2/F3/FE/NASCAR/IndyCar, and the sites render `probability`
straight as a percentage, so a reader adding up the win column got 200%. The
flagship had **already found and fixed this** in 2026-07, but the fix lived in
`projects/f1-predictions/models/calibration.py` rather than in the shared package,
so every cloned series inherited the calibration step and none inherited the fix.
`renormalize_market_struct` now lives in `motorsport_core.calibration`, every
series' `_calibrate_markets` calls it **unrounded** (rounding first reintroduces
the drift), and `probability_mass` is the corpus-level regression test. **The
general rule: a fix that belongs to every series goes in `packages/`, not in the
project where it was found.** Per-file schema tests all passed the whole time.

The near-miss is worth internalising: three schema mirrors *did* assert a
probability sum — on `rawProbability`, the empirical Monte-Carlo frequency,
which is coherent by construction and was never the broken field. The field the
site renders is `probability`. **A test one identifier away from catching this
passed cleanly for a month.** When you assert on a published number, assert on
the one the page actually shows;
`test_published_probabilities_sum_to_their_market` now does, in every project.

## Frontend specifics

- All sites are static exports — client-only libs must live in `"use client"`
  components; never import fs-based data loaders (`lib/<slug>data.ts`, `lib/registry.ts`)
  from client components. `.npmrc` pins `legacy-peer-deps=true` — do not delete it.
- **Shared design system**: F1's `website/src/components/{ui,magicui}` is canonical;
  every other site **including the hub** carries byte-identical copies enforced by
  `node scripts/sync_shared_ui.mjs --check` in CI — add each new site to its TARGETS in
  the same change that copies the site. A deliberate per-site divergence goes in
  `TARGET_EXEMPTIONS` **with its reason**, not in the global `SITE_SPECIFIC` set (which
  drops the file from the gate everywhere). Theming happens ONLY via each site's
  `styles/tokens.css` accent tokens (F1 `#E10600`, F2 `#1E9BD7`, F3 `#D9A441`,
  FE `#1E1AF0`, NASCAR `#FFD659`, IndyCar `#D31217` — light accents need near-black
  `--accent-ink`, deep accents need brightening hovers).
  Charts (`components/charts/`) are per-site adapted, deliberately NOT drift-gated.
- **Chart colour is validated, not chosen.** Every site defines `--viz-model`,
  `--viz-baseline`, `--viz-cat-3`, `--viz-reference`, `--viz-field` and
  `--viz-seq-1..5`, measured against all three chart surfaces with `--pairs all`;
  the numbers are in [`DESIGN.md`](DESIGN.md) §1.4 and in each `tokens.css`. Two rules:
  the categorical scale **stops at three** (a fourth hue fails CVD separation — fold the
  tail into `--viz-field`), and model/baseline are **always direct-labelled** because
  their tritan separation is ΔE 5.7, below the floor. Never use the site accent for one
  of two series — it is already the site's identity.
- **Evidence components are shared and synced**: `EvidencePanel`, `BaselineLadder`,
  `StatusBanner`, `EmptyState`, `Skeleton`, `format.ts`. `EvidencePanel` is deliberately
  **not a tab** and renders on every page showing a forecast. `format.ts` enforces
  absent-renders-as-absent (`—`, never `0`) and there are tests.
- **Every site has a Jest suite** (`npm test`), including a synced shared suite under
  `src/__tests__/shared/` that asserts the honesty rules rather than that components
  render. `@testing-library/dom` is declared as a **direct** devDependency on every
  site: it is a peer of `@testing-library/react`, and `.npmrc`'s `legacy-peer-deps=true`
  means npm will not install it transitively.
- **Every site has `error.tsx`, `not-found.tsx`, `global-error.tsx`, `manifest.ts`,
  `robots.ts` and `sitemap.ts`.** `global-error.tsx` renders its own `<html>`/`<body>`
  with inline styles — at that point the root layout is gone and the stylesheet may be
  what failed.
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
