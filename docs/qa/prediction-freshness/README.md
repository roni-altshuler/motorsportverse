# F1 prediction context verification

Base: `9e77298597cf6d66d39f2d4e3b935bd3a97e678b` (merged PR #15).
This change reads existing F1 artifacts and changes presentation only. There is
no new provider request, model run, training, ranking, probability or data field.
The factor and strategy calculations, values and forecast publication gate stay
in place. Preview pages now expose their stored export context.

## Artifact semantics

- `rounds/round_16.json.generatedAt`: `2026-06-27T17:06:41Z`, the ranking
  export time. Its qualifying source is `model estimate`, weather is `static`,
  and qualifying availability is false. All 22 driver factor lists are absent.
- `probabilities/round_16.json.generatedAt`: `2026-09-27T01:06:55Z`, the
  separate probability export time. It does not establish that rankings or
  inputs were refreshed. The reverse ordering receives the reverse warning.
- Round 15 records verified grid provenance, available qualifying input and
  API weather. These labels describe stored metadata, not a new source check.
- The current schema publishes no forecast input cutoff. Export time, weekend
  phase and matching export timestamps cannot supply one. The panel says
  **Not published** for the cutoff on both known and incomplete exports.
- Loading, an unavailable probability file, an absent timestamp, an invalid
  timestamp and a conflicting round/season identity are separate states. Times
  without a timezone and impossible calendar dates are rejected. Valid offsets
  are compared as instants and rendered in UTC, without inferring freshness.
- Qualifying/weather contradictions stay visible. A missing weather source is
  unverified, without the previous fallback to a static estimate. Weather labels
  here describe ranking inputs, independently of other page weather displays.

## Local checks

Existing locked F1 dependencies were reused through a worktree-local
`node_modules` symlink. No dependency, lockfile, workflow or security change.
Node 20.20.2 / npm 10.9.9; Next 16.1.6; Chromium 151.0.7922.173.

From `projects/f1-predictions/website`, using the pinned Node binary:

```sh
node node_modules/jest/bin/jest.js --runInBand
node node_modules/eslint/bin/eslint.js .
node node_modules/typescript/bin/tsc --noEmit
PAGES_BASE_PATH=/motorsportverse/projects/f1 node node_modules/next/dist/bin/next build --webpack
```

Results: **239 tests passed in 15 suites**, including 23 new artifact/context
regressions. Lint, types and a clean production static export passed. The local
build used existing committed prebuild images; CI runs the standard build.
The Python source and every published data file are unchanged. Shared UI drift,
edited-source formatting, harness syntax and whitespace checks passed.

## Browser verification

```sh
node scripts/qa/prediction_freshness.mjs \
  projects/f1-predictions/website/out /tmp/motorsport-prediction-freshness-delivery-qa \
  /workspace/motorsportverse-fastf1-workspace/projects/f1-predictions/website/out
```

The last argument is optional and captures the unchanged base preview card.
The runner serves only the local static export, blocks external requests and
does not alter DOM or committed data. Negative controls clone the original
JSON in memory and change metadata only; they are explicitly marked in the
[complete case matrix](browser-qa.json).

**32/32 cases passed**: 1440×1000 and 375×812, each with normal and reduced
motion. Eight cases per variant cover actual navigation, missing metadata,
unavailable file, invalid time, older probability export, identity conflict,
contradictory sources and delayed loading. Four real-artifact journeys use the
visible calendar card, check the preview gate, visit round 15, change a driver
comparison, use keyboard focus, expand the existing strategy view and return
to round 16. All are free of application/page errors, horizontal overflow and
write requests. The headings are unobscured by the sticky race band.

External image requests are blocked and their expected resource errors are
counted separately. The controlled unavailable-file case records its expected 404. The runner preserves caught route-error logs as well as uncaught page
errors; failures persist route, body and screenshot. Source hashes pin the
tested application and existing JSON. Repeated console resource messages are
compacted into counts; accessibility snapshots remain for all four real
journeys. Full local reports remain in the output directory.

| View    | Before                             | After                                       |
| ------- | ---------------------------------- | ------------------------------------------- |
| Desktop | [Preview card](desktop-before.png) | [Context panel](desktop-actual-journey.png) |
| Mobile  | [Preview card](mobile-before.png)  | [Context panel](mobile-actual-journey.png)  |

Controlled mobile states: [missing](mobile-missing-metadata.png),
[invalid time](mobile-invalid-time.png), [conflicting sources](mobile-source-conflict.png).
The captures use existing black/hairline tokens, monospaced timestamps and
textual uncertainty labels. Color is supplementary; times use semantic `time`
elements and the status is announced politely.

## Retained failures and limits

An initial build overlapped a parser correction. Its bundle retained an unbound
`verified` reference, while tests ran against corrected source. Browser QA
caught the route error boundary. The [exact caught stack](initial-build-failure.json)
is retained; the initial export remains at
`/tmp/motorsport-freshness-initial-export`. A clean rebuild from stable source
removed that stale compiled code; the complete final browser run passes.
The harness also needed case-insensitive checks for CSS uppercase text and a
visible calendar-card selector instead of a hidden desktop header link.
Neither harness correction changes application behavior.

No independent real-source availability, input-cutoff enforcement, model
accuracy, calibration or causal-factor claim is added. The historical mobile
hydration event documented by PR #15 remains unattributed. No production
workflow was dispatched and no merge is authorized by this PR.
