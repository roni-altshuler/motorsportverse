# Changelog

All notable changes to MotorsportVerse are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The shared
packages (`motorsport-core`, `motorsport-data`) follow [SemVer](https://semver.org/); the
projects and websites are versioned by maturity level instead — see [GOVERNANCE.md](GOVERNANCE.md).

Entries are grouped by the part of the monorepo they touch, because a change to
`motorsport-core` is load-bearing for every project while a change to one site is not.

## [Unreleased]

### Fixed

- **Calibrated probabilities did not sum to the size of the set they describe.**
  Per-competitor isotonic calibration does not preserve the simplex, so published win
  markets totalled anywhere from 0.50 to 2.00 across F2, F3, Formula E, NASCAR and
  IndyCar — and the sites render `probability` straight as a percentage, so a reader
  adding up an F3 feature-race win column got 160%.

  The flagship had **already found and fixed this** in July 2026, but the fix lived in
  `projects/f1-predictions/models/calibration.py` rather than in the shared package, so
  every cloned series inherited the calibration step and none inherited the fix.
  `renormalize_market_struct` now lives in `motorsport_core.calibration`; each series'
  `export._calibrate_markets` calls it unrounded (rounding first reintroduces the drift);
  `motorsport_core.integrity`'s `probability_mass` check is the corpus-level regression
  test. All five series regenerated — 274 integrity checks pass with no waivers.
  Full write-up in [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

- **Name-keyed baselines attached to the wrong model block.** NASCAR and IndyCar publish
  two model blocks (`race` and `racePostQuali`) but one set of baselines, which scores the
  pre-qualifying forecast. `motorsport_core.evidence` picked the block by iterating a set,
  so it could compare the post-quali model against the pre-quali baseline — a difference
  that would read as model drift. `_primary_race_type` now prefers `race` explicitly.

- **`NumberTicker` could publish a stat tile stuck at its start value** — usually `0` —
  when the in-view trigger never fired (headless capture, prerender, unusual engines).
  The hub carried a failsafe; the canonical F1 copy did not, so five sites went without
  it. Promoted to canonical and synced. This is the scroll-reveal-fails-closed bug in its
  most misleading form: a wrong *number* rather than a blank space.

- **The scaffolded projects' seams could never have been wired up.** They declared
  `motorsport_core.interfaces.Predictor` while calling the `motorsport_data` DataSource's
  `season`/`round`/`results` — two different ABCs with the same name. They now implement
  the core `calendar`/`grid`/`results` contract, with tests asserting conformance.

- **A missing `code` beside a real `name` is no longer read as a placeholder entrant.**
  The first integrity run reported twelve real Chrome Valley drivers as junk rows because
  the empty string is in the placeholder token set. Identity is now judged as a whole.

### Added

- **Repository governance layer.** `SECURITY.md` (private reporting, workflow hardening,
  third-party data rules), this changelog, GitHub issue forms
  (`bug_report` / `feature_request` / `new_series`), a pull-request template, and a
  `.pre-commit-config.yaml` running the same ruff configuration CI runs.
- **`DESIGN.md`** — the ecosystem design reference in [getdesign.md](https://getdesign.md/)
  format: tokens, type, spacing, components, motion, and the honesty rules that are also
  design rules. `docs/design-system.md` now points at it rather than restating a subset.
- **`docs/EVIDENCE.md`** — the standing rules for accuracy claims: baselines are never
  deleted, calibration gates the product, a backtest is labelled a backtest, and a
  regression blocks promotion.
- **`motorsport_core.evidence`** — builds one `EvidenceBlock` per project from
  `forward_eval/season.json` plus the baseline metrics, so every site renders the same
  model-vs-baseline panel from the same published artifact instead of each site
  reimplementing the comparison.
- **`motorsport_core.integrity`** — corpus and publication integrity checks that run over a
  project's published `website/public/data/` tree: probability simplex sums, calendar
  coverage, chronological ordering, duplicate and placeholder entrants, calibration-gate
  consistency, baseline presence, and forecast/result disjointness.
- **`scripts/validate_published_data.py`** — repo-wide runner for the above; exits non-zero
  on any failure and is wired into CI.
- **Frontend evidence components** in the canonical shared set: `EvidencePanel`,
  `BaselineLadder`, `EmptyState`, `StatusBanner`, `Skeleton`, and `format.ts`
  (absent renders as absent). Synced to every series site by the existing drift gate.
- **Error and not-found routes** on all nine sites, plus a web app manifest, `robots.ts`
  and `sitemap.ts` where they were missing (hub, Chrome Valley, Prism Cup).
- **Frontend test harness** on every site — Jest + Testing Library, shared tests for the
  synced components and per-site tests reading each site's committed JSON. `npm test` in
  CI. There were previously **zero** frontend tests anywhere in the repo.
- **`test_published_probabilities_sum_to_their_market`** in every project's
  `test_website_data_schema.py` — asserts the **calibrated** market sums, which is what
  the site renders. Three projects already asserted a sum, but on `rawProbability`: the
  empirical Monte-Carlo frequency, coherent by construction and never the broken field.
  A test one identifier away from catching the defect above passed for a month.

### Changed

- `scripts/sync_shared_ui.mjs` now also manages the ecosystem hub's `components/ui/`
  (already byte-identical, now gated) and the new shared evidence components.
- The ecosystem hub gained `robots.ts` / `sitemap.ts` parity with the series sites.

## [0.3.0] — 2026-07-11 — Fantasy fun projects

### Added

- `projects/chrome-valley-racing` and `projects/prism-cup-karting` — fully simulated,
  interactive fan-made leagues with original IP-safe naming and fan-made disclaimers.
  Registry category `fantasy`; deterministic seeded regeneration at deploy time; no cron
  and deliberately outside the drift gate.

## [0.2.0] — 2026-07-10 — Phase 0: complete the universe

### Added

- `projects/nascar-predictions` — full product: DNF-composition hazard model, the 2026
  Chase title Monte Carlo and the 2017-25 elimination format for backtests, playoff panel
  gated on `historical_backtest/playoffs.json:gate.pass`.
- `projects/indycar-predictions` — full product, snapshot-primary: the curated verified
  history for 2012-2026 *is* the ground truth (no public API), with dual oval/road-street
  form and a per-season curation report.
- `projects/formula-e-predictions` — full product on the pulselive API, with doubleheader
  handling and street/circuit strata.
- `projects/f3-predictions` — the golden template for cloning a new series.

### Changed

- F2 brought to golden-template parity, including the reverse-top-10 sprint grid.
- F1 post-quali overhaul: `gridProvenance` on every published round, a self-correcting
  freeze that re-freezes until a verified real grid exists, the quali-gap candidate model,
  and honest baselines on the accuracy page.
- All six implemented series promoted to **production** maturity.
- `deploy-website.yml` assembles six sites into one GitHub Pages artifact.

## [0.1.0] — 2026-06-16 — Monorepo foundation

### Added

- `packages/motorsport-core` — calibration (Plackett-Luce), championship Monte Carlo,
  standings, Elo, conformal intervals, evaluation, drift, promotion and leakage guards.
- `packages/motorsport-data` — the canonical pydantic schema, the `DataSource` ABC, the
  DuckDB history store and the shared FIA feeder scraper.
- The registry (`registry/projects/*.json` + JSON schema) as the catalog source of truth.
- The ecosystem hub website and `scripts/new_project.py` scaffolder.
- The F1 flagship merged in with full git history under `projects/f1-predictions/`.
