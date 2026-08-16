<!-- Thanks for contributing to MotorsportVerse. Please fill this out so reviewers have context. -->

## Summary

<!-- What does this PR do, and why? Link the issue it closes. -->

Closes #

## Scope

- [ ] `packages/motorsport-core` — **load-bearing for every project**
- [ ] `packages/motorsport-data` — **load-bearing for every project**
- [ ] One project (which: ______ )
- [ ] Several projects
- [ ] Ecosystem hub (`website/`) or registry
- [ ] Shared UI set (synced to every series site)
- [ ] CI / cron / deployment
- [ ] Docs only

## Type of change

- [ ] `fix` — bug fix (no breaking change)
- [ ] `feat` — new feature
- [ ] `refactor` — behaviour-preserving internal change
- [ ] `docs` — documentation only
- [ ] `chore` / `ci` / `build`

## How was this tested?

<!-- The exact commands you ran and what you observed. Pipelines run as modules from the
     project directory; pin OMP_NUM_THREADS=1 for anything importing xgboost. -->

- [ ] `ruff check packages projects scripts`
- [ ] `pytest` for every package/project touched
- [ ] `python scripts/build_registry.py` (if the registry changed)
- [ ] `node scripts/sync_shared_ui.mjs --check` (if any shared component changed)
- [ ] `python scripts/validate_published_data.py` (if any export changed)
- [ ] `npm run build` + `npm test` for every site touched
- [ ] `node scripts/shoot.mjs` screenshots reviewed (for visual changes)

## If this changes a model or a probability

<!-- Delete this section if it does not. See docs/EVIDENCE.md. -->

- Metric, and the **baseline** it is measured against:
- Rounds scored, and whether the comparison is walk-forward:
- Does `promotion_decision` say promote?
- [ ] No regression against the served model on the shared rounds
- [ ] Baselines (last-race, grid-order) are still published and still visible in the UI
- [ ] The calibration gate still reflects reality (`calibration_summary.json.applied`)

## If this changes published JSON

- [ ] The site's TypeScript types were updated in the same change
- [ ] The pydantic mirror in `tests/test_website_data_schema.py` was updated in the same change

## UI changes

<!-- Add before/after screenshots (npm run shoot). Delete if N/A. -->

## Checklist

- [ ] Follows [CONTRIBUTING.md](../CONTRIBUTING.md) and [DESIGN.md](../DESIGN.md)
- [ ] No fabricated data — sparse coverage stays genuinely missing
- [ ] No implementation details in user-facing copy (no "Plackett-Luce", "XGBoost", "Monte Carlo")
- [ ] No betting language; educational framing preserved
- [ ] Wrong-event guards still cover any new or changed live source
- [ ] No secrets or `.env*` committed
- [ ] `CHANGELOG.md` updated if behaviour or a public surface changed
- [ ] Registry entry updated if a project's maturity changed (see [GOVERNANCE.md](../GOVERNANCE.md))
