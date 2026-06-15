# Governance & maturity levels

MotorsportVerse projects advance through five maturity levels (defined in
`registry/schema/maturity.schema.json`). A project's level is recorded in its
`registry/projects/<slug>.json` entry and surfaced as a badge in the catalog.

## Levels

| Level | Meaning | Criteria to enter |
|---|---|---|
| **concept** | Registered idea; no code yet | A valid registry entry exists |
| **in-development** | Scaffold + data source in progress | Project folder exists; `DataSource` started; not yet end-to-end |
| **experimental** | Runs end-to-end | A `Predictor` produces forecasts for a real round; accuracy not yet validated |
| **production** | Validated & live | Forward-eval over ≥1 season, a live website, and an automated update pipeline |
| **archived** | Frozen / superseded | No longer maintained; kept for reference |

Today: **F1 = production**, **F2 = in-development**, all others = **concept**.

## Promotion rules

- Moving up a level is a PR that edits the project's registry entry; CI validates
  it via `scripts/build_registry.py`.
- **experimental → production** additionally requires: a published forward-eval
  report, a deployed website, and a scheduled update workflow.
- Any project may be moved to **archived** if unmaintained for two seasons.

## Shared-package stewardship

`motorsport-core` and `motorsport-data` are the load-bearing dependencies of
every project. Changes to their public APIs:

- must keep existing project tests green (CI runs all project test suites);
- follow SemVer — breaking changes bump the major version and are announced in
  the package changelog;
- prefer additive evolution (the schema uses `extra="ignore"` precisely so new
  fields don't break consumers).

## Decision-making

While the ecosystem is small, maintainers reach decisions by consensus on PRs.
The flagship (`f1-predictions`) is the reference for design questions: when in
doubt, do what F1 does.
