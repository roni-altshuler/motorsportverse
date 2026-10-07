# Locked-install audit for PR #13

The eight locked-install failures are resolved. All 11 sites were installed from
their committed locks and checked on **Node 20.20.2 / npm 10.9.9**, matching the
supported Node 20 CI line, in the same saved cloud executor.

## Exact base comparison

For F2, Formula E, IMSA, IndyCar, MotoGP, NASCAR, WEC and WRC, the base
`b9408e3a56bd08e51220709aae5f017dabcda272` manifests and lockfiles were copied
to isolated temporary directories with their existing `.npmrc`. Each actual
`npm ci --ignore-scripts --no-audit --no-fund` exited **1 / EUSAGE**, both with
the original Node 24/npm 11 tooling and with supported Node 20/npm 10.

The first six errors were the same in each site:

```text
npm error Missing: @testing-library/dom@10.4.2 from lock file
npm error Missing: @testing-library/jest-dom@6.9.1 from lock file
npm error Missing: @testing-library/react@16.3.3 from lock file
npm error Missing: @types/jest@30.0.0 from lock file
npm error Missing: jest@30.5.2 from lock file
npm error Missing: jest-environment-jsdom@30.5.2 from lock file
```

Each base install reported **310 missing packages**, including the transitive
test dependency tree. These omissions also existed at the initial PR head
`871d1df7c300b9f9eb1b9b76984f1beab58905b2`; the source-map security update
did not cause them. Base and initial install-head manifests were identical;
the later lint follow-up changes only ten lint scripts.

The repair materializes those already-declared dev dependencies: six root
metadata entries and 310 dev-only locked packages per affected site. Every
existing package entry is preserved byte-for-byte at the JSON-object level,
including versions, resolutions and integrity. No dependency declaration, direct dependency,
production dependency version or access setting changes. The authorized
source-map-js 1.2.2 update remains present in all 11 locks.

The website CI matrix now uses **`npm ci`** in place of `npm install`. The old
command silently repaired these omissions, allowing green website checks while
fresh locked installs failed. The new command makes the actual install the
regression gate; no production workflow was edited or dispatched.

## Supported checks after repair

Every command below ran with Node 20.20.2/npm 10.9.9, respecting the existing
`legacy-peer-deps=true` setting. `npm ci` left every lockfile's SHA-256 unchanged.

| Site | Clean `npm ci` | Frontend tests passed | Types | Static build | Installed source-map-js |
| --- | --- | ---: | --- | --- | --- |
| F1 | Pass | 130 | Pass | Pass | 1.2.2 |
| F2 | Pass | 130 | Pass | Pass | 1.2.2 |
| F3 | Pass | 126 | Pass | Pass | 1.2.2 |
| Formula E | Pass | 108 | Pass | Pass | 1.2.2 |
| IMSA | Pass | 108 | Pass | Pass | 1.2.2 |
| IndyCar | Pass | 120 | Pass | Pass | 1.2.2 |
| MotoGP | Pass | 108 | Pass | Pass | 1.2.2 |
| NASCAR | Pass | 108 | Pass | Pass | 1.2.2 |
| WEC | Pass | 108 | Pass | Pass | 1.2.2 |
| WRC | Pass | 108 | Pass | Pass | 1.2.2 |
| Hub | Pass | 117; 8 skipped | Pass | Pass | 1.2.2 |

Commands: `npm ci --no-audit --no-fund`, `npm test -- --runInBand`,
`npm run typecheck`, `npm run build`. The F1 build includes its prebuild asset
steps. Root `ruff check packages projects scripts`, offline archive export
`--check`, and shared-UI drift checks also pass. No generated chart/registry
changes are included.

The rebuilt F1 static export passed the actual desktop/mobile Chromium flows
again on this toolchain: real local data, keyboard selection, swap, repeated
navigation, reduced motion, portrait fallback and the explicitly injected
loading/error/retry/empty/wrong-session cases. The
[Node 20 browser report](qa/archived-lap-comparison/browser-qa-node20.json)
retains external proxy failures. No external image access was bypassed, and no
page exceptions or local resource failures occurred.

## Original base lint findings and their subsequent repair

Before the lint follow-up, full F1 ESLint exited 1 with five errors and one
warning. The exact base files were linted through the same installed toolchain
and compared with the initial comparison/install head. Their normalized
structured findings were identical:

| File | Rule | Line | Severity |
| --- | --- | ---: | --- |
| `jest.config.js` | `@typescript-eslint/no-require-imports` | 4 | Error |
| `jest.setup.js` | `@typescript-eslint/no-require-imports` | 1 | Error |
| `src/components/theatre/RaceTheatre.tsx` | `react-hooks/refs` | 111, 112, 113 | Three errors |
| `src/lib/driverData.ts` | `@typescript-eslint/no-unused-vars` | 69 | Warning |

Those four files were identical to base at that point. The comparison's seven
changed/new F1 frontend files reported **zero errors and zero warnings**.

The other ten sites' `npm run lint` exited 1 because their script invoked
`next lint`, unsupported by their locked Next 16.1.6 CLI. For example the hub says:

```text
Invalid project directory provided, no such directory: /workspace/motorsportverse-lap-comparison/website/lint
```

The follow-up [lint repair](LINT_TOOLING_REPAIR.md) replaces those unsupported
commands with `eslint`, adopts the existing flagship configuration and fixes
the listed errors without suppressions. All 11 lint commands now pass. Manifest
changes are limited to the ten lint scripts; dependency declarations remain
unchanged. The CI matrix now runs lint and type checks explicitly.

The [machine-readable evidence](qa/archived-lap-comparison/locked-install-checks.json)
records the exact base error snippets, counts, scope, tested lock hashes,
command exits, test totals, timings and base/head lint messages.

## CI and branch protection

All runs on the previous exact head `871d1df7` completed successfully:
[push CI](https://github.com/roni-altshuler/motorsportverse/actions/runs/37618244217),
[PR CI](https://github.com/roni-altshuler/motorsportverse/actions/runs/37618396900),
and [F1 CI](https://github.com/roni-altshuler/motorsportverse/actions/runs/37618396965).
Those earlier website jobs used `npm install`; they are not substituted for the
repaired head's `npm ci` checks. New-head run links and completion status belong
in the draft PR's body so adding CI results does not change the tested head.

PR #13 stays draft for independent review. Main and held PR #12 are unchanged.
