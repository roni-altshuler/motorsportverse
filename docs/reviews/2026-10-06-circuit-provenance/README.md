# Circuit provenance guard — 6 October 2026

This is the approved fallback for the proposed cross-series circuit explorer.
The inventory found no existing geometry with complete source-session/layout and
reuse evidence. An interactive explorer was therefore **not shipped**. Existing
SVG map loaders now reject unreviewed/conflicting geometry; the raw corpus remains
unchanged. F1's generic fallback outline is replaced by a compact unavailable
state, using the original series tokens. F2/F3's existing disclosure remains
keyboard accessible and no longer claims shared geometry is ready.

See [the coverage table and prerequisite](../../CIRCUIT_GEOMETRY.md) and the
machine-readable [coverage audit](coverage-audit.json). Stored coverage is
43/168 calendar rounds; eligible coverage is 0/168. The audit reports six
Austria/Silverstone identity conflicts, three ambiguous Hungaroring corner-number
representations, 34 unreviewed paths and 125 missing paths. Le Mans has no website
or calendar and is recorded separately.

## Verification

- **1,157 frontend tests passed**, with **eight existing hub skips**, across all
  ten series websites plus the hub. Wrong season/series/venue/layout, conflicting
  outlines, missing/incomplete evidence, changed coordinates, malformed corners
  and real stored duplicates are covered. Synthetic accepted-path tests are
  explicitly QA-only and their reviews are never in the product registry.
- All **11 site typechecks and static builds passed**. F1 used
  `next build --webpack` directly to avoid its unrelated image-generation
  prebuild; it produced the real static site used below. The other sites used
  their existing build command. The previously missing Jest matcher type import
  is supplied by the new DOM test. Four unsupported Testing Library `exact`
  options in existing hub role queries were removed; those queries already use
  exact string-name matching.
- ESLint passed for the new guard, unavailable component, tests, audit script and
  adapted map loaders. The full F2 RaceDetail file retains its preexisting
  `react-hooks/set-state-in-effect` error in the archival overlay effect,
  unchanged from merged base `71ee2a6`. Broader legacy-component lint cleanup is
  outside this guard. Two existing `prefer-const` errors in the touched F2/F3
  loaders were corrected without changing behavior.
- Shared-copy drift and `git diff --check` passed. All **407 published-corpus
  checks passed**. No package manifest, lockfile or published-data file changed.
  Six existing site locks omit declared test dependencies; local installs used
  `npm install --ignore-scripts --package-lock=false`, preserving those files.
- The ordinary circuit inventory exits 0 after producing its report. The same
  command with `--require-verified` correctly exits **1** for current coverage.
  CI labels the ordinary inventory **report only**; green regression tests are
  not a claim of verified map coverage.

## Actual browser QA

`node scripts/qa_circuit_geometry.mjs <output-dir>` serves the actual static
exports and uses existing Playwright with system Chromium. The clock is fixed
to 6 October 2026 at 12:00 UTC. It checks **48 actual race-page cases**: four rounds
per F1/F2/F3, two viewports (1440/390 pixels) and both motion preferences.

All map rejection, readable-state, clipping, horizontal-overflow, native keyboard
disclosure and reopening assertions passed. The native disclosure is the existing
F2/F3 interaction; F1's absence is static. Homepages contain no gated-out circuit
ribbon, and there are **zero replay requests**. The unavailable state has no SVG,
image, controls or animation, including while closed/offscreen. This does not
claim that other preexisting page animations or `RaceTheatre` redraws were fixed.

[F1 desktop](f1-desktop.png) · [F1 mobile](f1-mobile.png) ·
[F2 desktop](f2-desktop.png) · [F2 mobile](f2-mobile.png) ·
[F3 desktop](f3-desktop.png) · [F3 mobile](f3-mobile.png).

The [full report](browser-qa.json) retains errors and failed resources rather
than hiding them. F1 had **zero page errors** in all four viewport/motion runs,
but remote-asset console failures remained. F2/F3 reduced-motion runs each
recorded the existing React hydration error #418, with asset failures in both
motion modes. This is not an error-free whole-site QA result. The prior merged
coverage work reproduced F2/F3 hydration errors at the unchanged base; see
[its baseline comparison](../2026-10-06-result-coverage/baseline-comparison.json).

A separately built archive of merged main `71ee2a6` was compared with the final
F1 export under the same fixed clock and both viewport sizes. After waiting for
the actual race heading, the base rendered one Silverstone circuit SVG and the
guarded build rendered none. Both builds had zero page errors in that paired
home/race check; see [the comparison](baseline-comparison.json). The baseline
comparison does not establish that the base SVG depicted the correct venue.

## Scope preserved

PR10's exact head was verified as an ancestor of its merge commit
`71ee2a6d15a80d1b3617501a031caa2f2efcc527`. Its remote branch was deleted only with
an exact-head lease for `e9267b8`; the PR and local recovery branch remain.
This work starts on that merged main commit in a separate branch. No merge,
production dispatch, new credentials, broad provider collection, model change,
data replacement or laptop-branch transfer occurred.
