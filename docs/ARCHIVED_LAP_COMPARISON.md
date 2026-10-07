# Archived lap comparison review

The proposed F1 `/compare/laps` route compares two drivers' stored race laps
sector by sector. It is a review-branch feature, not a deployment claim. The
existing hero, forecasts, replay, circuit geometry and held PR #12 are unchanged.

## Scope and provenance

The fixed input is
[`2025_Monaco_R.parquet`](../projects/f1-predictions/features/data/lap_cache/2025_Monaco_R.parquet),
already committed on base `b9408e3a56bd08e51220709aae5f017dabcda272`.
It contains 1,403 rows for 20 drivers, with lap and three sector durations.
Its SHA-256 is
`efb689f9d0f6a9c8133c54b37171084314cb812460b710ab4c206326ee6dd56a`.
The source is a FastF1-derived snapshot; these timings are not independently
certified official fastest laps.

[Formula 1's event page](https://www.formula1.com/en/racing/2025/monaco) verifies
the race date, 25 May 2025. The
[official result page](https://www.formula1.com/en/results/2025/races/1261/monaco/race-result)
verifies participant identities, including Yuki Tsunoda, absent from the current
season's shared identity constants. Those pages were used only for identity/date
verification; no result table was imported. No provider collection or live API
access occurred.

The offline exporter reads only this local parquet file. It rejects wrong-year
rows and unknown driver identities, excludes missing/nonpositive/nonfinite or
inconsistent timings, and selects the fastest complete **same row** for each
driver. Integer milliseconds preserve signed differences without floating-point
rounding surprises. Equal times have a deterministic sector-tuple tie break.
The JSON records complete/stored row counts, source fingerprint and absent fields.

There are no lap numbers, tyres, pit/track status or accuracy flags in the input.
Different drivers' selected rows may come from different race conditions. The UI
states those limits and avoids a clean-lap, official-fastest-lap or model-accuracy
claim. Existing portraits identify drivers and may be from a later season;
Tsunoda uses the shared fallback without a request for a nonexistent portrait.

Existing `telemetryData.sectorTimes` was not reused: the current exporter can
default its telemetry extraction to 2025 qualifying without retaining year/session
provenance. Existing forecast `DriverComparison` is a different feature.
The design reuses `HUDPanel`, `DriverPortrait`, native selectors, timing formatting
and the site's typography/hairlines. The
[f1-race-replay README](https://github.com/IAmTomShaw/f1-race-replay) informed the
driver-selection/comparison concept; no desktop GUI code, artwork or paid live
OpenF1 functionality was transferred. The Instagram reel itself could not be
opened by the research tool, so it is not represented as independently watched.

## Verification on 7 October 2026

The Vercel verification skill guided the boundary trace:
static `/compare/laps` → local JSON HTTP 200 → session/source and duration
validation → two stored records → rendered sectors and signed lap delta.
The successful browser flow uses the actual exported file. For Norris/Russell,
the source gives 73,221/73,405 ms; the page shows +0.184s, with a −0.007s second
sector delta. Swapping reverses the signed lap difference.

| Check | Verified result |
| --- | --- |
| Offline exporter `--check` | Artifact reproduces from the committed input |
| F1 Python `ruff check .` | Passed |
| Full F1 Python tests | 1,087 passed, 2 skipped; exit 0 |
| F1 frontend tests | 130 passed |
| Changed F1 frontend files: ESLint / Prettier | Passed |
| F1 types / static build | Passed; final export rebuilt after the landmark correction |
| F3 frontend tests / types / static build | 126 passed / passed / passed |
| Hub frontend tests / types / static build | 117 passed, 8 skipped / passed / passed |
| Actual Chromium, desktop 1440 × 1000 and mobile 390 × 844 | Passed all comparison flows |

Run [`qa_session_comparison.mjs`](../scripts/qa_session_comparison.mjs) after
building F1. It serves the actual static export, selects seven driver pairs,
checks duplicate-choice exchange, native keyboard selection, Enter-to-swap,
2px visible focus, source disclosure, desktop hover/mobile menu navigation,
history back/forward, portrait fallback and no horizontal overflow. Reduced
motion produces zero animations in the comparison. The loading, HTTP 503/retry,
empty and wrong-session screenshots are **explicit local-response fault
injections**, not claims that those states occurred at the provider.

Screenshots were visually inspected:
[desktop](qa/archived-lap-comparison/desktop-comparison.png),
[mobile](qa/archived-lap-comparison/mobile-comparison.png),
[keyboard focus](qa/archived-lap-comparison/desktop-keyboard-focus.png),
[reduced motion](qa/archived-lap-comparison/desktop-reduced-motion.png),
[portrait fallback](qa/archived-lap-comparison/mobile-portrait-fallback.png),
[loading](qa/archived-lap-comparison/mobile-loading.png),
[HTTP error](qa/archived-lap-comparison/mobile-http-error-retry.png),
[empty](qa/archived-lap-comparison/mobile-empty.png), and
[wrong session](qa/archived-lap-comparison/mobile-wrong-session.png).
The [raw browser report](qa/archived-lap-comparison/browser-qa.json) retains
console/network observations. No page exceptions or local resource failures
occurred. The existing global Singapore flag failed through the cloud proxy;
calendar navigation also encountered existing external flag/Wikimedia image
failures. These are not hidden behind a clean-console claim. All comparison data
and portraits are local.

The saved cloud executor was verified usable again at **11:54:43 UTC** after a
lifecycle disconnection notice. The same worktree, edits and Chromium were present;
no environment switch occurred.

## Narrow dependency patch and remaining gates

[GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
affects `source-map-js` versions ≥1.0.0 and <1.2.2. The indexed source-map offset issue can hang
the event loop. All 11 site locks contained 1.2.1; each changes only that leaf's
version, resolved tarball and integrity to 1.2.2. No manifest, direct dependency,
override, other lock package or credentials change. Fresh F1/F3/hub installs
confirmed 1.2.2, followed by the checks above. Presence in the build dependency
tree does not establish exploitation of the static deployed site.

Remaining repository checks are not green:

- Full F1 ESLint reports five errors in **unchanged** `jest.config.js`,
  `jest.setup.js` and replay ref assignments, plus an existing unused-variable
  warning. The same base files reproduce those findings; changed files pass.
- F3 and hub's existing `npm run lint` invoke unsupported `next lint`.
- Fresh `npm ci` fails for F2, Formula E, IMSA, IndyCar, MotoGP, NASCAR, WEC and
  WRC: existing manifests require six Jest/testing-library packages missing from
  their base locks. Baseline F2 `npm ci --legacy-peer-deps` reproduces this; the
  other base locks have the same missing package entries. Their build/type/test
  checks could not run on a fresh locked installation. This patch leaves those
  unrelated lock inconsistencies for separate work rather than claiming green
  cross-series installs.

Keep the new PR **draft** for the parent's independent review and resolution of
remaining check gates. No main update, merge, production dispatch, external
announcement, research edit, provider scraping or production model retraining
was performed. Existing model unit tests ran on their test fixtures.
