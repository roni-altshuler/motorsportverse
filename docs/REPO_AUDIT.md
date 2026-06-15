# Repository audit

Hygiene audit of the MotorsportVerse monorepo (2026-06-15), conducted after the
branding + F2 expansion work. Status legend: ✅ fixed · 📌 documented (intentional)
· ⬜ no action needed.

## Summary

The repository is clean. All on-disk generated artifacts are already correctly
ignored; three real issues were found and **fixed**; the known cross-repo code
duplication is **intentional and documented**.

## 1. Generated artifacts / temp files

All present artifacts are covered by `.gitignore` — nothing uncommittable is at
risk of being tracked.

| Artifact | Found | In `.gitignore` | Status |
|---|---|---|---|
| `__pycache__/`, `*.pyc` | yes | yes | ⬜ ignored |
| `.pytest_cache/`, `.ruff_cache/` | yes (per-package) | yes | ⬜ ignored |
| `*.egg-info/`, `.mypy_cache/` | no | yes | ⬜ |
| `website/node_modules/`, `.next/`, `out/` | yes | yes (incl. `projects/*/website/*`) | ⬜ ignored |
| `*.duckdb`, `.DS_Store` | no | yes | ⬜ |
| editor temp (`*.swp`, `*~`, `*.orig`) | none | — | ⬜ |

## 2. `.gitignore` correctness — ✅ FIXED (was a silent risk)

The original rule `data/` (unanchored) matches a `data/` directory **at any
depth**, so it would have shadowed `website/public/data/registry.json` and
`projects/*/website/public/data/f2.json` — the committed catalog/data source of
truth. A prose comment claimed these were kept in VCS but no rule backed it.

**Fix:** anchored the rule to `/data/` (only the top-level DuckDB store dir) and
documented the committed-generated files explicitly. See
[`.gitignore`](../.gitignore).

## 3. Intentionally-committed generated files — 📌 documented

| File | Generator | Why committed |
|---|---|---|
| `registry/index.json` | `scripts/build_registry.py` | catalog index the website reads |
| `website/public/data/registry.json` | same (prebuild) | served by the static site |
| `projects/f2-predictions/website/public/data/f2.json` | `f2_predictions.export` | served by the F2 static site |

These are deterministic outputs kept in VCS so the websites build without a
Python step. Regenerate with the commands above.

## 4. Duplicated code

### Cross-repo (motorsport-core ← f1_predictions) — 📌 intentional, documented

Most core modules were extracted by **copying** from `f1_predictions` during the
foundation phase (`calibration`, `registry`, `drift`, `elo`, `conformal`,
`reliability`, `hierarchical_bayes`, `leakage`, `promotion`, `features/*`). F1
keeps its own copies — by design, F1 production behavior must not change.

> **Follow-up (out of scope here):** re-point `f1_predictions` to consume
> `motorsport-core` instead of its private copies, then delete the copies from F1.
> This is the single largest dedup opportunity and is deliberately deferred so F1
> stays risk-free.

### Within motorsport-core — ✅ FIXED

`brier_score()` was defined identically in both `calibration.py` and
`reliability.py`. Consolidated: `reliability.brier_score` is now the single
implementation and `calibration` re-exports it (so
`from motorsport_core.calibration import brier_score` still works).

### Intentional parity — 📌 not a defect (determinism ✅ fixed)

`scripts/build_registry.py` (Python) and `scripts/build_registry_node.mjs`
(Node) implement the same validation deliberately: Python for CI/local, Node so
the website `prebuild` needs no Python. Kept in sync by their shared schema.

> ✅ The two generators originally emitted *different* output (the `generated_by`
> field, and Python's `ensure_ascii` escaping vs Node's raw UTF-8), so whichever
> ran last dirtied `registry/index.json` in the working tree. Both now write a
> shared `generated_by` value with `ensure_ascii=False`, producing **byte-identical
> output** — verified with `diff`.

## 5. Public-API / dead-code review

No module is truly dead — every module is exercised by tests and is intended
public library API for sport projects to import. One mismatch was fixed:

- ✅ `motorsport_data/__init__.py` listed `store` and `sources` in `__all__` but
  did not import them. Now imported (cheap — `store` only pulls DuckDB lazily on
  `HistoryStore` construction).

The newly added core modules (`standings`, `championship`) are consumed by F2 and
covered by their own tests, so they are live, not speculative.

## 6. Stray / throwaway files — ⬜ none

No scratch files, no half-created project directories, no `.output`/`.orig`
leftovers. `templates/project-template/` is the legitimate new-project skeleton.

## 7. File-count snapshot (excludes node_modules / caches / build output)

| Area | Files |
|---|---|
| `packages/motorsport-core` | 16 src modules + 11 test files |
| `packages/motorsport-data` | 6 src modules + 1 test file |
| `projects/f2-predictions` (python) | 6 src modules + 2 test files |
| `projects/f2-predictions/website` | ~38 ts/tsx + config |
| `website` (ecosystem) | ~43 ts/tsx + config |
| `registry` | 13 JSON (index + 11 projects + 2 schema) |
| `docs` | 9 markdown |
| `scripts` | 4 (registry ×2, new_project, generate_brand) |

## Actions taken this pass

1. ✅ Anchored the `data/` ignore rule to `/data/` (correctness).
2. ✅ Deduped `brier_score` (calibration re-exports reliability).
3. ✅ Fixed `motorsport-data` `__all__`/import mismatch.
4. 📌 Documented the intentional F1↔core duplication + deferred dedup follow-up.

All 106 Python tests pass and `ruff check` is clean after these changes.
