# Energy sandbox verification

The proposed F1 `/circuits#energy-sandbox` feature was built and checked in the
saved cloud worktree `/workspace/motorsportverse-energy-sandbox` on 9 October 2026. Repository identity is `roni-altshuler/motorsportverse`; the branch starts
at main `12fdd87f09f167f77762f6804d8f3b7822cfc971`. The reported workspace
disconnect recovered in the same environment: commands, the worktree and
Chromium were available. No environment switch or duplicate branch was needed.

## Numerical and frontend checks

- **256 tests / 16 suites pass**, including 17 sandbox tests and conservation,
  finite/nonnegative flows, exact capacity/charge bounds and demand accounting
  across **720 scenarios**. [Aggregate log](tests.log).
- Full F1 ESLint and TypeScript checks pass. Changed code, QA script and new
  technical documentation pass Prettier; `git diff --check` passes.
- The actual local production static export passes: **85 pages**.
  [Build log](build.log). The unchanged Recharts prerender warning remains;
  the new charge chart is original SVG and does not use Recharts.
- Shared UI copies are unchanged and `sync_shared_ui.mjs --check` passes.
- All **240 tracked F1 public-data, data and model files** checked before/after
  retain their SHA-256 hashes. No provider reads, training, model promotion,
  dependency/lock changes, workflow changes or production dispatch are included.

Commands used the existing pinned Node 20.20.2 runtime and unchanged locked
dependency tree. From the F1 website, the checks invoke the existing Jest,
ESLint, TypeScript and Next CLI entrypoints:

```bash
node node_modules/jest/bin/jest.js --runInBand
node node_modules/eslint/bin/eslint.js
node node_modules/typescript/bin/tsc --noEmit
PAGES_BASE_PATH=/motorsportverse/projects/f1 node node_modules/next/dist/bin/next build --webpack
```

The final fractional-capacity regression was first observed failing:
`0.73389 × 100 / 100` rounded to `0.7338900000000002`, above capacity.
[Failing test log](fractional-capacity-before.log). Normalizing the percentage
before multiplication preserves the exact full bound; regeneration also caps
the stored state after addition. The final suite and browser test exercise that
specific input. No invalid user value is silently clamped into a valid input.

## Production-export browser journeys

[Machine-readable report](browser-qa.json) records the exact source SHA-256
hashes, export build ID, exported HTML hash, Chromium version, viewport and raw
error/request logs. Four journeys cover desktop **1440 × 1000** and mobile
**375 × 812**, each under normal and reduced motion:

- Actual race → circuit client navigation and energy-section anchor; direct
  reload gives deterministic defaults without hydration or route errors.
- Default analytical results, units, a visible synthetic/educational disclosure
  and the bounded charge trace; one responsive SVG is visible at each width.
- Keyboard number adjustment, keyboard reset and Enter without navigation.
- Zero flow, empty/full limits and a fractional full-capacity regression.
- Blank/out-of-range inputs hide previous results, while valid decimals and
  reset restore them; error labels are associated with their controls.
- Keyboard details, six cycle rows and real ArrowRight scrolling within the
  mobile table, with no horizontal document overflow.
- Exact official learning links, external-tab labels and the account disclosure.
- The local-capture anchor settles below the expanded header, and the original
  fictional demo and clear controls still work by pointer. The old shared
  workspace component and global navigation are unchanged.
- Reduced motion has no running sandbox animation. Assumption calculation
  performs no data/API requests. Existing local navigation/static prefetches
  are recorded separately; GET/HEAD requests are retained in the raw log.

All four final journeys pass with **zero page errors, unexpected console
errors, first-party HTTP failures or non-GET/HEAD requests**. External requests
are deliberately blocked. The existing race header's flag image causes expected
browser resource errors; those remain in the raw log and are accepted only for
the exact intercepted URL plus the exact network-abort message. Caught React
errors and all other console errors fail the check.

Screenshots are captured in separate real tabs at the same viewport and motion
preference, with the actual entered values. This keeps full-document capture's
temporary viewport resizing out of the interactive journey. The after images
were inspected for readable axes, labels, focus, layout, constraints and tables.

From repository root:

```bash
node scripts/qa/energy_sandbox.mjs projects/f1-predictions/website/out /tmp/energy-sandbox-qa
```

An optional third path is a prior export for before screenshots. The retained
baseline is the saved PR #16 export, whose application source matches the merged
base; the report pins its circuit HTML hash. Final local production build/QA is
independent evidence: the repository's PR CI skips the F1 site build, and its
dedicated F1 CI tests Python. Neither is described as a frontend production build.

## Screenshots

| Desktop                                      | Mobile                                      |
| -------------------------------------------- | ------------------------------------------- |
| [Before: local captures](desktop-before.png) | [Before: local captures](mobile-before.png) |
| [Sandbox overview](desktop-overview.png)     | [Controls and focus](mobile-controls.png)   |
| [Empty limit](desktop-empty-limit.png)       | [Charge chart](mobile-chart.png)            |
| [Energy ledger](desktop-ledger.png)          | [Full limit](mobile-full-limit.png)         |
|                                              | [Energy ledger](mobile-ledger.png)          |

## Retained diagnostics

Earlier failures are kept for review instead of erased by a passing rerun:

- [Initial browser log](first-browser-attempt.json): sandbox checks passed;
  an assertion incorrectly required zero errors for deliberately blocked
  external flag images. The final harness distinguishes only those exact aborts.
- [Anchor movement](anchor-before.json) and
  [measured geometry](anchor-before-diagnostic.log): the first short-anchor
  offset straddled the existing navbar's 80 px collapse threshold. Header-height
  changes and scroll anchoring kept capture buttons moving. The page-local
  offset is now 160 px, with actual pointer activation verified in every variant.
- [Overly narrow anchor assertion](anchor-position-check-before.json) and
  [isolated-camera check](anchor-position-check-isolated-camera.json): the
  corrected anchor stayed stable, but header expansion can add 32 px after the
  native jump. The final assertion checks visible placement below the header
  and remaining below the collapse threshold, rather than requiring one pixel
  position. This does not claim a global navbar repair.
- [Initial prefetch assertion](prefetch-check-before.json): a mobile run
  observed existing Next navigation prefetches after scrolling. The final
  harness retains that traffic, allows only known local navigation/static
  requests, and rejects data/API or other calculation-time requests.

No real battery behavior, course-content reuse rights, model accuracy or live
deployment is established by these checks. Parent review and merge remain pending.
