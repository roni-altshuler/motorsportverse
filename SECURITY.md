# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for anything that
could put users or data at risk.

- Use GitHub's [private vulnerability reporting](https://github.com/roni-altshuler/motorsportverse/security/advisories/new)
  ("Report a vulnerability" under the repository's **Security** tab), or
- Email the maintainer at `shenorrlab@technion.ac.il` with `[SECURITY]` in the subject.

Please include: a description, reproduction steps or a proof of concept, the affected
package/project/workflow, and the potential impact. We aim to acknowledge reports within
**5 business days** and to provide a remediation timeline after triage.

## Supported versions

This is a monorepo deployed from `main`. Only the latest `main` is supported; fixes are
rolled forward rather than backported. The shared packages (`motorsport-core`,
`motorsport-data`) follow SemVer per [GOVERNANCE.md](GOVERNANCE.md), but security fixes
land on `main` first and are not backported to earlier majors.

## Scope

**In scope:** everything in this repository — the two shared packages, every project under
`projects/`, the ecosystem hub and per-series websites, the registry tooling under
`scripts/`, and the GitHub Actions workflows under `.github/workflows/`.

**Out of scope:** vulnerabilities in the upstream data providers this repo reads
(fiaformula2.com, fiaformula3.com, the Formula E pulselive API, cf.nascar.com, Jolpica,
FastF1, …), and findings that require a compromised developer machine or privileged local
access.

## Secrets & configuration

- **No secrets in the repo.** Every project is configured through environment variables
  (`<SPORT>_SEASON`, `<SPORT>_USE_POSITION_HEAD`, `F1_CANDIDATE_MODEL`, `PAGES_BASE_PATH`, …).
  Never commit `.env*` files or keys.
- The prediction pipelines read **public, unauthenticated** endpoints. No project requires a
  provider API key, and adding one must go through a PR that documents where the secret is
  stored (GitHub Actions secrets) and why an anonymous path is not sufficient.
- Server-only values must **not** use the `NEXT_PUBLIC_` prefix — that ships them in the
  client bundle. Every site is a static export, so anything reachable from a page is public
  by construction.
- Committed data under `projects/*/data/` and `projects/*/website/public/data/` contains
  race results and model output only — no PII.

## Workflow hardening

The scheduled `*-update-predictions.yml` crons commit to `main`. Because a compromised
workflow is a supply-chain problem rather than a site defect, three rules hold:

1. **Schema-gated commits.** A cron may only commit if the regenerated artifacts still
   validate against the project's `tests/test_website_data_schema.py` mirror. A run that
   produces malformed JSON fails instead of publishing.
2. **Freshness gates.** Each cron no-ops when the upstream source returns nothing new,
   rather than publishing a degraded or empty snapshot.
3. **Wrong-event guards.** Every live source verifies the returned payload's identity
   (round / date / venue / race id) against the config calendar *before* any snapshot
   write. This exists because a real incident published one race's grid as another round's
   prediction; see `tests/test_wrong_event_guards.py` in every project.

Third-party actions are pinned by major version and must come from `actions/*` or a
reviewed source. A PR that introduces a new action needs a note on why.

## Handling third-party data

The repo reads public endpoints and republishes derived numbers. Per project convention:

- Provider fields are never synthesized or placeholdered — missing data stays missing and
  is labelled in the UI. See the "don't fake data" rule in [CLAUDE.md](CLAUDE.md).
- Scrapers are rate-respectful and cache to a committed snapshot so downstream builds never
  touch the network.
- Nothing in this repository is betting advice, and no odds provider is ingested.

## Disclosure

We follow coordinated disclosure: please give us a reasonable window to ship a fix before
any public write-up. Credit is offered to reporters who wish to be acknowledged.
