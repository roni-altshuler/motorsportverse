# Circuit workspace selection — 2026-10-10

On base `ebfa752ad1f4c29f437358f099c354e0b74c9f6e`, driver positions were
noninteractive SVG circles with hover titles. Clicking a position did not select
its driver. At 390px wide, Jamie's list button was 451–452px below the map.
[Baseline observations](baseline.json) record four actual Chromium cases.

The F1 `/circuits` workspace now uses 44px native buttons at the supplied
positions. Touch, Enter and Space share selection with the existing driver list.
A selected-name readout and clear action sit immediately below the map; its
fictional/unverified source stays visible in the map header. Snapshots remain
manual under both motion preferences. Names, colors and positions come from the
capture; no event identity, telemetry accuracy or data rights are certified.

The outline keeps its native SVG transform. Button centers use the same supplied
rotation and world-Y flip. Missing and out-of-view positions create no map
controls; the list still exposes those drivers. It also resolves coincident
positions without moving a sample to make space. Series changes clear capture
and selection. No reviewed artwork, circuit configuration or new series route
is introduced. The unused licensed-image explorer and its eligibility gates,
legacy outlines, quarantines and published data remain unchanged.

## Browser evidence

[Final observations and source/export SHA-256s](final.json) cover six real
static-export cases: 1440px desktop, 390px touch and 320px touch, each under normal
and reduced motion. The source inputs are the unchanged original fictional demo
and original QA-only messages embedded in the runner.

- Native touch and keyboard actions select, toggle and clear the same driver.
- Every measured hit target is 44×44px; keyboard outlines are 2px solid.
- Independent SVG screen matrices confirm rotated-source alignment within 0.016px.
- Missing, off-map, absent and overlapping samples retain truthful list access.
- All 11 series-selector options start with unavailable map coverage; no fake
  event map appears. No horizontal overflow, page exception or failed local HTTP
  resource was observed in these cases.
- One external flag-image request per case is deliberately blocked to keep the
  runner local. Its console error and broken header image remain visible in the
  records/screenshots; consoles are not claimed clean.

The [broader workspace regression summary](workspace-regression.json) records
four additional desktop/mobile motion cases using the existing runner. Its map
absence queries are scoped to the workspace, and its static-position check now
measures the actual HTML controls. It retains menu navigation, local import,
invalid/late-input recovery and manual snapshot checks. Its external flag/image
requests failed at the saved environment's proxy; the consoles are not clean.
The [compressed original record](workspace-regression.json.gz) preserves every
request and error, with its SHA-256 in the summary. No real user capture was tested.

[Before, mobile](before-mobile.png) · [After, mobile](after-mobile.png) ·
[After, 320px](after-narrow.png) · [After, desktop](after-desktop.png)

## Checks and remaining blocker

The [local check matrix](local-checks.json) records all 55 commands and log hashes:
11 installs, lints, type checks and production builds pass; ten full Jest suites
pass. Overall, 2,274 tests pass, four fail and eight are skipped. ESLint reports
29 warnings and no errors. The [original logs](local-check-logs.tar.gz) include the
isolated baseline failure run. Exact-head CI links are in the PR description.
Shared component/tests follow the F1-canonical sync contract; the production
workspace is still mounted only on F1. Each touched site is checked with a locked
install, ESLint, its full Jest suite, types and production build at its actual
Pages base path, using Node 20.20.2 / npm 10.9.9. Generated assets are restored in
the isolated worktree rather than committed. No provider refresh is run.

**F1's full suite has four pre-existing failures** in `predictionFreshness.test.tsx`:
hard-coded June/September dates and factor assumptions no longer match the
October 10 committed round-16 artifacts. The same four fail when that untouched
test runs alone. Its imported components, library and data match base exactly;
the ten workspace tests pass. Assertions and prediction data are unchanged.
This PR stays draft for independent review; it is not merge-ready while this
check is red. [Baseline failure evidence](freshness-baseline.json) records the
untouched input hashes and failing test names.

## Reproduce

```sh
node scripts/sync_shared_ui.mjs --check
cd projects/f1-predictions/website
npm ci
npm run lint
npm test -- --ci --runInBand
npm run typecheck
PAGES_BASE_PATH=/motorsportverse/projects/f1 npm run build
cd ../../..
node scripts/qa/circuit_selection.mjs /tmp/circuit-selection-final final
node scripts/qa_circuit_workspace.mjs /tmp/circuit-workspace /motorsportverse/projects/f1
```

Run the same install/lint/test/types/build commands in the other ten touched site
directories, using `/motorsportverse` for the hub and
`/motorsportverse/projects/<slug>` for each series. Full command logs, their
SHA-256 inventory, browser records and original checkout-preservation snapshot
are retained at `/tmp/motorsportverse-circuit-explorer` in the saved environment.

To repeat the baseline, create a separate checkout at the base SHA, copy the PR's
new browser runner into it, install/build F1 at the same base path, then run the
runner with `baseline` as its last argument. Compiled export hashes identify the
actual captures; a new build can generate a different Next build ID.

Public Pages reachability and a lawfully obtained real capture are separate
checks. No production job, paid service, upstream code vendoring, model training,
licensed-map acquisition or laptop-only work transfer is performed here.
