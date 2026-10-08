# Lint tooling repair for draft PR #13

All 11 sites now run supported ESLint commands and pass. This follow-up resolves
the original five F1 errors and errors exposed when lint actually began checking
the other sites. It stays on `feat/archived-lap-comparison`, separate from held
PR #12. No lint rule is disabled, downgraded or broadly ignored.

## Tooling and exact original F1 errors

The ten non-flagship sites used `next lint`, removed from their locked Next 16
CLI. Their scripts now invoke `eslint`, matching F1. Each adopts an exact copy
of F1's existing flat configuration: Next core-web-vitals, Next TypeScript, and
only the same generated-directory ignores (`.next`, `out`, `build`,
`next-env.d.ts`). There were no other site ESLint configuration files to preserve.
Dependency declarations and locks are unchanged by this lint follow-up.

The original errors reproduced on exact base `b9408e3a` and install head
`ce47bfb8810d612807a1a681940103a049bae763`:

| Original location | Rule / count | Repair |
| --- | --- | --- |
| F1 `jest.config.js:4` | `@typescript-eslint/no-require-imports` / 1 | Rename to `jest.config.mjs`; import `next/jest.js` and export the same configuration. |
| F1 `jest.setup.js:1` | `@typescript-eslint/no-require-imports` / 1 | Import jest-dom through ESM; other setup behavior is preserved. |
| F1 `RaceTheatre.tsx:111–113` | `react-hooks/refs` / 3 | Synchronize playing, speed and focused-driver refs in `useLayoutEffect`, after commit and before the next animation frame. |
| F1 `driverData.ts:69` | `@typescript-eslint/no-unused-vars` / 1 warning | Remove the unused private `FINISHED_STATUSES` constant. |

All 11 Jest configurations/setup files use the same ESM conversion so the shared
rule set can check them. Test options, environments and existing mocks remain
unchanged. The CI website matrix now runs `npm run lint` and
`npm run typecheck`, alongside the previously added locked-install gate.

## Additional errors exposed during the repair

After the original F1 fixes and ESM conversion, the first full inventory found
16 more errors. Their exact files, lines and messages are retained in
[checks.json](qa/lint-repair/checks.json).

| Location | Rule / count | Repair and preserved behavior |
| --- | --- | --- |
| F1 replay loading | `react-hooks/set-state-in-effect` / 1 | Derive loading from the resolved round/data-root/reduced-motion request identity; completion still commits the same data and autoplay decision. No effect-driven loading reset. |
| F2, F3, Formula E, IndyCar, MotoGP, NASCAR and WRC `RaceDetail` | `react-hooks/set-state-in-effect` / 7 | Select archive overlays by data root and round, only while an archive is selected. Returning to the current season immediately selects baked props; the existing async cancellation guard remains. |
| Hub `CommandPalette` | `react-hooks/set-state-in-effect` / 1 | Reset the active option in the query-change event, alongside its query update. Close still clears both. |
| Hub `EcosystemDiagram` | `react-hooks/refs` / 4 | Memoize the array of created refs by displayed node count, retaining the existing identities without reading or mutating a ref during render. This component is not mounted on the current landing page. |
| Hub `RaceCentre` | `react-hooks/set-state-in-effect` / 1 | Subscribe to the external UTC-day clock with a server snapshot; seed shared-link/preferences once from a stable browser snapshot, with guarded render-time state adjustment. Keep popstate handling, minute refresh, filtering and storage/privacy fallbacks. |
| Two WRC marketing strings | `react/no-unescaped-entities` / 2 | Escape apostrophes as `&apos;`; displayed wording is unchanged. |

The page structures, styling, race data, model behavior and replay geometry are
unchanged. Correct archive selection can retain a previously loaded, matching
archive while its refresh runs; it cannot reuse one from another data root or
round. No provider collection, security-setting change or production job occurs.

## Verified checks

All checks ran in the same saved cloud environment using **Node 20.20.2 /
npm 10.9.9**. Each fresh `npm ci --no-audit --no-fund` left its lock hash unchanged.

| Site | Clean install | Lint errors / warnings | Tests passed | Types | Full static build |
| --- | --- | --- | ---: | --- | --- |
| F1 | Pass | 0 / 0 | 130 | Pass | Pass |
| F2 | Pass | 0 / 4 | 133 | Pass | Pass |
| F3 | Pass | 0 / 4 | 126 | Pass | Pass |
| Formula E | Pass | 0 / 4 | 108 | Pass | Pass |
| IMSA | Pass | 0 / 1 | 108 | Pass | Pass |
| IndyCar | Pass | 0 / 4 | 120 | Pass | Pass |
| MotoGP | Pass | 0 / 4 | 108 | Pass | Pass |
| NASCAR | Pass | 0 / 5 | 108 | Pass | Pass |
| WEC | Pass | 0 / 1 | 108 | Pass | Pass |
| WRC | Pass | 0 / 1 | 108 | Pass | Pass |
| Hub | Pass | 0 / 0 | 122; 8 skipped | Pass | Pass |

Total: **1,279 frontend tests passed, 8 skipped**. New regressions cover query
selection reset, reopening the palette, browser UTC day versus build day,
midnight expiry, history links after filtering, corrupt/blocked local storage,
current/archive changes, late archive responses and round changes.

The remaining 28 warnings are recorded, not hidden: 18 native-image warnings,
7 calendar dependency warnings and 3 unused-import/type warnings. They do not
fail the existing rule configuration. F1 and the hub have zero warnings.
Root Ruff, shared-UI drift and offline archive-export `--check` pass.
The ten evidence artifacts reproduce on **Python 3.11.16**, matching CI's 3.11
line. Under local Python 3.12 the unchanged MotoGP baseline mean rounds to
3.272438 rather than 3.272437; exact base reproduces this difference. No
evidence artifact or numeric implementation is altered to hide it.

## Browser regressions and review boundary

Run [qa_lint_repair.mjs](../scripts/qa_lint_repair.mjs) after rebuilding the sites.
It serves actual static exports and uses system Chromium at 1440 × 1000 and
390 × 844. The report retains page, console and resource errors, including
external proxy failures; no external access is bypassed.

All 18 replay/hub/series flows completed with zero page exceptions. The series
routes retain 102 observed portrait-404 events whose files are absent on exact
base `b9408e3a`; the existing portrait fallback renders. Local JSON/script/style
failures are still test failures. MotoGP's 390px mobile race page measures 406px
wide; that layout finding is recorded separately from the verified controls.
The other 17 viewports have no horizontal overflow.
An exact base application snapshot was also built in `/tmp` using a separate
physical install of the repaired lock (unchanged dependency declarations).
Its actual mobile Chromium route measures the same **406px** at **390px**.
[The base/head comparison](qa/lint-repair/motogp-baseline-overflow.json) and
[base screenshot](qa/lint-repair/motogp-exact-base-mobile.png) establish that
the overflow predates the lint repair. No CSS change is folded into this task.

The replay checks use the existing 2026 round-one file: paused cursor stability,
measured 1×/4× UI playback, repeated controls, ±5-second keyboard seek,
space play/pause, native range selection, focus redraw/restore and restart.
Mobile reduced motion remains gated until explicit play. These checks do not
certify existing geometry or source telemetry.

Hub checks use the actual published feed: historical shared link, saved follow
preferences after reload, filters/history, palette keyboard selection and
navigation, and a later browser date superseding the static snapshot date.
The seven changed race-detail sites are checked on their real current-season
round-one routes in both viewports. All seven public indexes offer only 2026;
archive switching is covered by explicit unit fixtures, not claimed as real
archived-season browser data.

The comparison route is also rechecked using
[qa_session_comparison.mjs](../scripts/qa_session_comparison.mjs), including the
clearly labeled loading/error/retry/empty/wrong-session fault injections.
Latest reports: [lint-repair browser QA](qa/lint-repair/browser-qa.json) and
[comparison regression QA](qa/lint-repair/comparison-browser-qa.json).
Screenshots: [replay desktop](qa/lint-repair/replay-desktop.png),
[replay mobile](qa/lint-repair/replay-mobile.png), and
[hub mobile](qa/lint-repair/hub-mobile.png).

The original series checks above did not verify the race body's painted
visibility. [The MotoGP mobile visibility follow-up](MOTOGP_MOBILE_VISIBILITY.md)
adds real scrolling and opacity/viewport/hit-test assertions for its podium,
12 probability rows and 31 classification rows. Four matched base/head mobile
cases pass in both motion modes; the shared 18-flow runner passes again.
Readable section pairs and retained pixel differences address the visual
review without claiming an application regression or changing application code.

PR #13 stays **draft** for independent parent review of the full lock/lint delta.
Main remains `b9408e3a`; held PR #12 remains `073fd947`. Exact new-head commit and
completed CI/check links belong in the PR body so reporting them does not move
the tested head. No merge or production dispatch.
