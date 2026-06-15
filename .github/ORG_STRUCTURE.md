# GitHub organization structure

MotorsportVerse starts as a **monorepo** (this repository) for fast iteration,
but every folder is built to graduate into its own repo under a
`motorsportverse` GitHub org — scverse-style — when it earns one.

## Recommended org: `github.com/motorsportverse`

| Repo | Source today | Purpose |
|---|---|---|
| `motorsportverse` | this repo | Monorepo / meta + ecosystem website + registry |
| `motorsport-core` | `packages/motorsport-core` | Shared ML & eval package (publish to PyPI) |
| `motorsport-data` | `packages/motorsport-data` | Schema + ingestion package (publish to PyPI) |
| `f1-predictions` | existing `f1_predictions/` | Flagship (transfer the existing repo) |
| `f2-predictions` | `projects/f2-predictions` | First expansion |
| `f3-predictions` … `motogp-predictions` | `registry` concepts | One repo per sport as it starts |
| `motorsportverse.org` | `website/` | Ecosystem site (or keep in the meta repo) |
| `.github` | — | Org-wide profile README, issue/PR templates, health files |

## Split path (monorepo → multi-repo)

Each `packages/*` and `projects/*` folder is self-contained (own
`pyproject.toml`/`package.json`, own tests), so extraction is mechanical:

```bash
# Example: graduate motorsport-core into its own repo, preserving history.
git subtree split --prefix=packages/motorsport-core -b split-core
# push split-core to github.com/motorsportverse/motorsport-core
```

After splitting the packages, projects depend on them via PyPI
(`motorsport-core>=0.1`) instead of editable local installs.

## Versioning & releases

- Packages follow SemVer and publish to PyPI on tag.
- Projects pin a compatible `motorsport-core` / `motorsport-data` range.
- The registry remains the single catalog source; the website reads it at build.

## Org-wide conventions

- MIT license across all repos.
- Branch protection on `main`; CI (lint + tests) required.
- Issue labels shared via the `.github` repo defaults.
- Every project repo carries a matching `registry/projects/<slug>.json` entry in
  the meta repo so it appears in the catalog.
