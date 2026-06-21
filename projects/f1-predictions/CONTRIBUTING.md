# Contributing to RaceIQ

Thanks for your interest in improving RaceIQ. This guide covers the workflow and
the standards CI enforces. For environment setup, start with
[`SETUP.md`](SETUP.md).

## Getting started

1. Fork and clone, then follow [`SETUP.md`](SETUP.md).
2. Create a branch off `main`: `git checkout -b feat/<short-description>`.
3. Make focused changes; keep unrelated edits in separate PRs.
4. Run the checks below before pushing.

## Local checks (must pass before a PR)

```bash
# Python
ruff check .              # lint (the same command CI runs)
pytest tests/ -q          # full suite

# Website
cd website
npm run lint              # ESLint
npx tsc --noEmit          # TypeScript typecheck
npm run build             # static export must succeed
```

## Standards

- **Python** — formatted/linted by [Ruff](https://docs.astral.sh/ruff/);
  configuration lives in [`pyproject.toml`](pyproject.toml). No unused imports,
  no undefined names. Type hints on new public functions; `mypy` config is in
  `pyproject.toml`.
- **TypeScript / React** — ESLint (`eslint.config.mjs`) + Prettier
  (`website/.prettierrc`). Run `npm run format` to auto-format.
- **Editor** — a root [`.editorconfig`](.editorconfig) standardizes indentation
  and line endings; most editors pick it up automatically.
- **Commits** — conventional prefixes (`feat:`, `fix:`, `docs:`, `chore:`,
  `refactor:`, `test:`). Keep messages imperative and scoped.

## The website ↔ pipeline data contract (important)

Data flows **Python → JSON → TypeScript**. The TypeScript interfaces in
[`website/src/types/index.ts`](website/src/types/index.ts) are the contract, and
the pydantic mirror in
[`tests/test_website_data_schema.py`](tests/test_website_data_schema.py) gates it
in CI.

When you change a Python output shape, in the **same PR**:

1. Update the matching TypeScript interface in `types/index.ts`.
2. Update the pydantic model in `tests/test_website_data_schema.py`.

New fields should be **optional** so older JSON snapshots still validate
(the pydantic models use `extra="ignore"`).

## Things to respect

- **Leakage discipline** — any feature that aggregates prior rounds must filter
  to rounds strictly before the current one and assert it via
  [`leakage.py`](leakage.py). See [`docs/ML_PIPELINE.md`](docs/ML_PIPELINE.md).
- **Calibration is honestly gated** — never report calibrated probabilities
  unless the gate trips. See [`docs/ML_PIPELINE.md`](docs/ML_PIPELINE.md).
- **Tech-stack scrub** — user-facing pages describe *what the model says*, not
  *how it's built* (no algorithm/library names in the UI). Implementation
  detail belongs in `docs/`.
- **Driver identity in the UI** — render drivers via the shared
  [`DriverPortrait`](website/src/components/standings/DriverPortrait.tsx)
  component and [`resolveDriverHeadshot`](website/src/lib/headshots.ts); don't
  re-introduce bare 3-letter codes as the primary identifier.
- **Static export only** — no server components, API routes, or runtime secret
  fetches in `website/`. All data is JSON loaded at build time.

## CI

Every push/PR runs [`/.github/workflows/ci.yml`](.github/workflows/ci.yml):
`ruff check .` + the full `pytest` suite. The website deploy and the
cron data-refresh pipelines are described in
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md#deploy).

## Reporting issues

Open a GitHub issue with steps to reproduce, expected vs actual behavior, and
(for UI issues) a screenshot. For data/image rights concerns, see the
attribution note in [`LICENSE`](LICENSE).
