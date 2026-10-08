# Root-route hydration investigation — 2026-10-08

The [historical mobile reduced-motion failure](earlier-mobile-hydration.log)
reported React #418 with an HTML mismatch. That older runner did not record the
event's route, timestamp or React stack. Those fields cannot be reconstructed.
The original event is **not established as external, benign or fixed**.

## What was actually compared

Before the repair, an isolated static build of main
`2a9152e9abe519cfbe51fbdd0d0eca2fa6e9e9a7` and the PR's `0041300` export each
completed 52 production browser cases without a hydration or other runtime
error: 20 ordinary cases, 16 with sixfold CPU throttling, and 16 with delayed
Flight delivery. Each case performs six hard/reload/soft navigation steps
between `/circuits` and `/race/12`; both mobile/desktop and reduced/normal motion
are represented. External requests are blocked, and only existing committed
site files are served. Script-delay cases preserve the script contents; the
streamed cases preserve the full HTML bytes and their order.

Eight development cases and an additional complete four-case local-capture
journey also passed. These non-reproductions do not explain the historical
event. An initial diagnostic harness failed to decode escaped asset URLs,
causing chunk 404s; those harness failures were corrected and excluded from
the comparison counts above.

## Independently proven bounded defect

This repository has no PageTransition component. Its installed Next renderer is
React `19.3.0-canary-f93b9fd4-20251217`, rather than the NBA investigation's
older renderer. The diagnostic lead was tested against this repository's actual
RootLayout and SmoothScrollProvider source instead of copying that component.

The isolated probe stubs the navbar, footer, live band, season provider and font
loader; CSS is ignored. It uses an original synthetic page, the installed Next
React renderer and a Flight-compatible pending child. The mocked scheduler
fulfills that child during a pinned hydration yield.

Before the repair, matching server/client markup reports #418 through
`replaySuspendedUnitOfWork`. Development output compares the expected `<main>`
with its own inner Suspense marker; both the main container and content are
replaced. Main and the original PR share the same RootLayout source hash:
`4971f5baf334937af88b655a8528f6c776de4b051122282b43125bead4185ab7`.

`RouteMain` retains the same main element, ID, tab index and classes. Its private
RouteContent component resolves the pending child on a component fiber before
the renderer can replay the main host element. It adds no DOM wrapper,
animation, delay, dependency change or warning suppression.

The regression compiles the actual RootLayout, RouteMain and
SmoothScrollProvider files in isolated child processes, in both production and
development modes. It proves:

- Matching markup retains the original main and content nodes without an error.
- Removing only the private child fiber from compiled source leaves the emitted
  server markup byte-identical, but reproduces #418 and replaces both nodes.
- Deliberately different server fixture text still reports a hydration mismatch
  and replaces that content. The repair does not hide real mismatches.

This proves and repairs a controlled root-layout replay defect. **It does not
establish the exact cause of the earlier unstructured browser event.**

## Reproduce

With existing F1 frontend dependencies, from its website directory:

```sh
npm test -- --runInBand src/__tests__/rootLayoutHydration.test.ts
NODE_ENV=production node ../../../scripts/qa/root_layout_hydration.cjs
NODE_ENV=development node ../../../scripts/qa/root_layout_hydration.cjs
NODE_ENV=production node ../../../scripts/qa/root_layout_hydration.cjs --without-child-boundary
NODE_ENV=production node ../../../scripts/qa/root_layout_hydration.cjs --different-server-text
```

From the repository root, after a production build with the real base path:

```sh
node scripts/qa/hydration_routes.mjs projects/f1-predictions/website/out /tmp/hydration-normal 20
HYDRATION_CPU_RATE=6 HYDRATION_THROW_OBSERVER=1 node scripts/qa/hydration_routes.mjs projects/f1-predictions/website/out /tmp/hydration-cpu 16
HYDRATION_STREAM_DELAY=1000 HYDRATION_THROW_OBSERVER=1 node scripts/qa/hydration_routes.mjs projects/f1-predictions/website/out /tmp/hydration-streamed 16
```

The browser diagnostic writes every case, route, viewport, preference, console
error, request and exception, including failed cases. Its opt-in debugger
observer reads exception scopes and resumes; it does not mutate app markup.
The full workspace runner now persists page-error observations immediately,
even when an assertion prevents its final report. Production observations and
controlled replay reports are recorded separately in
[hydration-checks.json](hydration-checks.json).

After the repair, 20 ordinary production cases and the complete four-case
workspace journey passed. F1's 216 frontend tests, lint, types and production
build pass. The browser negative control changes only a server fixture's
heading tag and catches four #418 HTML mismatches across desktop/normal and
mobile/reduced-motion cases, including exact route and stack observations.
It also verifies the opt-in throw-point observer. These deliberate fixture
failures are distinct from the unattributed historical event.

The next-reel audit remains separate from this repair. Existing factor panels
and strategy comparisons are already present. The next ranking snapshot lacks
per-driver factors and a published cutoff; its ranking-export and probability-
export timestamps differ. A future assumptions panel should expose those facts
using existing artifacts, not fabricate factors or simulate new rankings.
