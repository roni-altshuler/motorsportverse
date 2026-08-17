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
  Per-competitor isotonic calibration does not preserve the simplex, so published
  markets across nine of the ten live series were incoherent — worst win-market
  sums from 1.19 to 1.43, and the sites render `probability` straight as a
  percentage, so a reader adding up an F2 win column got 143%.

  The flagship had **already found and fixed this** in July 2026, but the fix
  lived in `projects/f1-predictions/models/calibration.py` rather than in the
  shared package, so every cloned series inherited the calibration step and none
  inherited the fix. `renormalize_market_struct` now lives in
  `motorsport_core.calibration` and composes with the small-sample
  regularisation from `b2765d9` instead of undoing it — the water-fill treats
  `CALIBRATION_PROB_FLOOR` as a lower bound, so scaling a market down cannot
  reintroduce the hard zeros that floor exists to prevent.

  The four newest products (MotoGP, WRC, WEC, IMSA) each normalised `win` alone,
  with a comment reasoning that top-k markets "legitimately sum to k". They
  should; calibration is exactly what stops them. Full write-up in
  [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

- **WRC's raw top-k markets never summed either.** Its championship-form prior
  used hand-assigned constants totalling 3.39 / 8.30 / 13.80 instead of 3 / 6 /
  10; blended 50/50 with a coherent model, the published *raw* values came out
  at exactly 3.195 / 7.150 / 11.900. Fixed at the cause — the prior is now
  water-filled to its own market size, so the ensemble stays coherent by
  convexity. `renormalize_market_struct` deliberately does not touch
  `rawProbability`, so a modelling bug cannot hide behind a presentation fix.

- **`--viz-cat-3` was not colour-blind safe, and the comment claiming it was
  cited a validator that did not exist.** The token block asserted measurements
  from `scripts/validate_palette.js`, which was nowhere in the repo. Written and
  run, it showed `#c25ba6` failing red-green separation against `--viz-baseline`
  (ΔE 11.9 protan, 14.7 deutan, floor 15) — two of three chart series
  indistinguishable to a colour-blind reader. Replaced with `#b75781` (ΔE 20.4
  minimum) and every number in the comment is now reproducible.

- **The evidence module could not read four of its own series.** Five published
  forward-eval shapes exist across the ecosystem — the flagship's top-level
  snake_case, the feeder shape, the name-keyed shape, MotoGP/WRC's `score`
  wrapper, and the endurance products' per-class arrays. Matching on the metric
  rather than the key name lets one function serve all five. Without it the
  flagship's own evidence panel would have rendered empty.

- **A time-bomb test in Formula E, and the CI blind spot that hid it.**
  `test_composite_qualifying_is_real_only` asserted that the *last round of the
  calendar* had no qualifying, as a stand-in for "a round not yet run". Commit
  `b0f4976` — a routine cron data update — completed the season and made that
  permanently false. It now asks for a round beyond the calendar, which is absent
  regardless of the date, and asserts the property its docstring actually claims.

  The structural half matters more: cron commits push with `GITHUB_TOKEN`, which
  by design does not trigger workflows, so **zero of the last 40 CI runs were for
  a data commit**. Each cron's own gate ran `test_website_data_schema.py` alone —
  and WEC and IMSA installed `pytest` without ever invoking it. Every cron now
  runs `scripts/validate_published_data.py` before committing, and the endurance
  crons gained the export/model gate they never had.

- **`NumberTicker` could publish a stat tile stuck at its start value** — usually
  `0` — when the in-view trigger never fired (headless capture, prerender,
  unusual engines). The hub carried a failsafe; the canonical F1 copy did not,
  so nine sites went without it. This is the scroll-reveal-fails-closed bug in
  its most misleading form: a wrong *number* rather than a blank space.

- **Name-keyed baselines attached to the wrong model block.** NASCAR and IndyCar publish
  two model blocks (`race` and `racePostQuali`) but one set of baselines, which scores the
  pre-qualifying forecast. `motorsport_core.evidence` picked the block by iterating a set,
  so it could compare the post-quali model against the pre-quali baseline — a difference
  that would read as model drift. `_primary_race_type` now prefers `race` explicitly.

- **A missing `code` beside a real `name` is no longer read as a placeholder entrant.**
  The first integrity run reported real drivers as junk rows because the empty string is
  in the placeholder token set. Identity is now judged as a whole.

- **`baselines_published` failed the endurance products for a baseline they do publish.**
  WEC and IMSA score per class and publish `overall.lastRace` / per-class baselines in
  `season.json` rather than a `baselines` block on every round file. The rule is that an
  accuracy number must have something to be compared against, not that the comparison
  lives in a particular file — a gate that fails correct data teaches readers to ignore
  the gate.

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
  on any failure and is wired into CI. 407 checks over 11 projects, no waivers.
- **`scripts/build_evidence.py`** — publishes `evidence.json` for every project from one
  implementation of the comparison, wired into all ten cron workflows so the artifact
  ships with the round it describes. `--check` fails CI when a published block is stale.
- **`scripts/validate_palette.js`** — the dataviz validator the token comments had been
  citing without it existing. CIEDE2000, Machado CVD simulation in linear light, WCAG
  contrast; `--ordinal` and `--pairs all` modes. Runs in CI.
- **Frontend evidence components** in the canonical shared set: `EvidencePanel`,
  `BaselineLadder`, `EmptyState`, `StatusBanner`, `Skeleton`, and `format.ts`
  (absent renders as absent). Synced to every series site by the existing drift gate.
- **Error, not-found and global-error routes** on all eleven sites, each naming the site
  the reader is actually on. `global-error` renders its own `<html>`/`<body>` with inline
  styles, because it is what shows when the root layout and the stylesheet are what failed.
  The hub gained the `manifest` / `robots` / `sitemap` trio the series sites already had.
- **Frontend test harness** on every site — Jest + Testing Library, with the shared
  component tests synced alongside the components they pin. `npm test` runs in CI across
  all eleven sites. There were previously **zero** frontend tests anywhere in the repo.
- **`test_published_probabilities_sum_to_their_market`** in every project's
  `test_website_data_schema.py` — asserts the **calibrated** market sums, which is what
  the site renders. Three projects already asserted a sum, but on `rawProbability`: the
  empirical Monte-Carlo frequency, coherent by construction and never the broken field.
  A test one identifier away from catching the defect above passed for a month.

### Changed

- `scripts/sync_shared_ui.mjs` gained a *required* tier. Its `ui` directory was
  intersect-only — a canonical file absent from a target was treated as an opt-out, which
  is right for a chart and wrong for the honesty primitives. A site quietly missing
  `format.ts` does not degrade gracefully; it renders a confident `0` where the value is
  absent. The gate now also covers the hub, whose copies were already byte-identical and
  simply ungated — which is exactly how it came to carry a `NumberTicker` failsafe that
  canonical lacked for months. An ungated identical copy is not a copy that stays
  identical, it is one nobody has diffed yet.
- CI replaced the single hub-only `website` build job with a matrix over all eleven sites
  running `npm test` then a production build. The flagship runs tests but not its build:
  its prebuild does image processing that belongs with its own deploy.

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
