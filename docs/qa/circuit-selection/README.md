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
The [compressed original record](final.json.gz) retains every measured Tab state;
the readable summary keeps the navigation order and relevant focus measurements.

- Native touch and keyboard actions select, toggle and clear the same driver.
- Natural Tab and Shift+Tab reach the map controls without programmatic focus.
  Enter on the visible import button produces a file-chooser event. Clear restores
  focus to the previously selected marker; when that sample is unavailable, focus
  stays on the named map-selection group and the next Tab reaches the snapshot input.
- Supplied positions exactly at all four **map viewport** edges retain their
  44px targets. Twenty-four probes reach the outer portion beyond the SVG bounds
  with the map centered in the browser viewport; no coordinate is clamped or moved.
- Every measured hit target is 44×44px; keyboard outlines are 2px solid.
- Independent SVG screen matrices confirm rotated-source alignment within 0.016px.
- Missing, off-map, absent and overlapping samples retain truthful list access.
- All 11 series-selector options start with unavailable map coverage; no fake
  event map appears. No horizontal overflow, page exception or failed local HTTP
  resource was observed in these cases.
- One external flag-image request per case is deliberately blocked to keep the
  runner local. Its console error and broken header image remain visible in the
  records/screenshots; consoles are not claimed clean.

[Before-focus observations](focus-baseline.json) reproduce six cases on the
original PR head: Clear left focus on `BODY`, and Tab reached a fully clipped
1px file input. The [compressed original record](focus-baseline.json.gz) retains
the observations and source/export hashes. The fixes restore focus and leave the
visible import button as the file chooser's keyboard stop. Its event subscription
gets a browser round-trip before raw Enter, avoiding the recorder's initial
interception race; app behavior was not changed for that recorder issue.

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
11 installs, lints, type checks and production builds pass; all eleven Jest suites
pass. Overall, 2,280 tests pass and eight are skipped. ESLint reports
29 warnings and no errors. The [original logs](local-check-logs.tar.gz) include the
isolated baseline failure run. Exact-head CI links are in the PR description.
Shared component/tests follow the F1-canonical sync contract; the production
workspace is still mounted only on F1. Each touched site is checked with a locked
install, ESLint, its full Jest suite, types and production build at its actual
Pages base path, using Node 20.20.2 / npm 10.9.9. Generated assets are restored in
the isolated worktree rather than committed. No provider refresh is run.

The original PR head reproduced four base failures in `predictionFreshness.test.tsx`.
Its scenarios accidentally imported changing round exports. A narrowly scoped
[deterministic test correction](freshness-correction.md) supplies explicit fixtures
while retaining all assertions; two added checks cover current-export timestamp
wiring and recorded factors. Base fails identically at June, September and October
clocks; the corrected suite passes 25/25 at each. F1's full suite now passes 260
tests. Production freshness logic, source data and model outputs remain unchanged.
[Historical baseline evidence](freshness-baseline.json) records the earlier test
and input hashes; [new diagnosis](freshness-diagnosis.json) identifies the exact
expected/actual values and unchanged production inputs. This PR stays draft for
independent parent review; no merge is performed.

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
