# Theme and navigation journeys

This audit starts from `46f14dbb38ed8ca72d597c33381f763a8fab79b3`, the remote
main revision containing the circuit workspace and archived lap comparison.
There were no open PRs at the start. Work lives on
`fix/theme-navigation-consistency`; main and the preserved local branches were
not rewritten. The separate laptop-only weekend-navigation work was not
available or transferred.

## Design policy and bounded fixes

[`DESIGN.md`](../DESIGN.md#9-what-not-to-add) intentionally specifies dark-only
sites. The hub uses its blue-black canvas, Inter body, Saira display, pill
controls and ambient background. Series sites keep their black canvas, serif
body, display/mono typography, flat surfaces and individual brand accents.
There is no appearance chooser to persist. The hub's soft/vivid/off ambient
setting is its existing persisted preference; its navigation behavior did not
need a product change. No light mode or replacement universal palette was added.

The baseline exported browser journey proved these defects:

| Area | Before | Change |
| --- | --- | --- |
| Hub project launch | White labels on F2, F3, NASCAR and WEC accents measured 3.12, 2.25, 1.40 and 1.77:1 | Choose white or the existing hub canvas ink by contrast; preserve accent backgrounds |
| Hub caption | Existing small feed note measured 4.39:1 | Lift the existing dim-ink token |
| Hub keyboard focus | Translucent crimson outline measured 1.75:1 | Use the existing bright accent-text token |
| Hub recovery | Undefined series-only style classes; zero border/padding on retry control; duplicate main landmarks | Use actual hub display, lead and ghost-button styles; render a section inside the layout's main |
| Series recovery | Actual static 404s contained two main landmarks on all ten sites | Preserve their styles and render recovery sections inside the layout's main |
| Root recovery | Hub changed to black/monospace; all eleven small diagnostic labels measured 3.66:1 | Keep the hub canvas and inline fallbacks; raise diagnostic ink to a readable neutral |
| Native appearance | Hub and NASCAR lacked the dark color-scheme metadata used by the other series | Declare their existing dark identity explicitly |
| Reduced-motion hydration | F2, F3, NASCAR, IndyCar and MotoGP emitted React #418 on initial navigation | Use one shared hydration-safe system-preference hook |
| Mobile navigation/layout | F1 closing drawer reached 710px in a 390px viewport; F1/MotoGP tab rows reached 395px; MotoGP header badges reached 406px | Independently keyed drawer layers, wrapping tab rows, and a bounded shared header action slot |

The F2 development build identified the hydration mismatch precisely:
`AnimatedNumber` rendered `0.0%` on the server and `16.7%` in the first
reduced-motion browser render. The server has no system media preference. The
hook now uses `useSyncExternalStore` with a stable server snapshot, honors the
browser preference after hydration and subscribes to later changes. The shared
sync gate now manages this hook alongside its regression tests. See the
[official React error reference](https://react.dev/errors/418).

Footer text already measured 13.08:1. Its CSS body style overrides the dim color
on the footer wrapper, so changing all series' dim tokens would have been an
unnecessary edit. Palette, body font and accents remained consistent along each
series' home/list/detail/profile/evidence journey. Those identities, header
styles, chart tokens, data, models and accuracy claims remain unchanged.

## Browser verification

[`scripts/qa_theme_journeys.mjs`](../scripts/qa_theme_journeys.mjs) serves actual
static exports at `/motorsportverse` and `/motorsportverse/projects/<series>`.
It clicks the hub directory, project details and existing Live demo links,
substituting only each launch link's origin with the local server. It follows
actual site links through calendar, an available race detail, standings,
available driver profile, accuracy/evidence, back, forward, reload and about.
WEC and IMSA have no published race links in their calendars; the report records
that limitation instead of fabricating detail data.

The same journey includes the F1 archived comparison and browser-local circuit
workspace. It covers a real stored comparison and driver selection, archive
loading, failed fetch and retry, empty comparison, circuit unavailable state,
fictional demo, delayed local import and cancellation, and malformed import.
Hub empty search and actual static 404 pages are included. Recovery style
fixtures render actual product fallback markup inside the real site shell;
isolated global fallbacks render their own HTML without the root stylesheet.
These fixtures verify markup/style, not an actual root error boundary trigger.

Fault fixtures are explicitly recorded: delayed local archive response, local
503, a QA-only archive copy with an empty driver array, delayed browser-local
`File.text`, and malformed original NDJSON. They are not published data or
provider responses. No historical timing values or imagery were invented.

The baseline report is a desktop/light-system/reduced-motion journey on the
original exports. All 55 recorded source hashes match the original main
revision. The separate baseline recovery probe used all ten real static 404
exports. Reports:

- [Baseline journey](qa/theme-journeys/before.json)
- [Series recovery baseline](qa/theme-journeys/series-recovery-before.json)
- [Baseline production-path builds](qa/theme-journeys/baseline-builds.json)
- [Final browser report](qa/theme-journeys/after.json)
- [Final local check matrix](qa/theme-journeys/local-checks.json)

Final validation and measured results are recorded after the completed run.

## Scope and limits

The server and browser are local saved-cloud tooling, not a public deployment
test. External requests are aborted and retained in the report. Existing local
portrait 404s are retained separately; the existing identity fallback is used.
Expected deliberate 404/503 fixtures are distinguished from unexpected HTTP
failures. No external image source was retried or bypassed.

The first styled animation frame's computed canvas is compared with the
hydrated page. This does not prove every pre-CSS pixel, eliminate normal font
swapping, or test every browser. No provider/model work, result refresh,
production dispatch or new external access was performed. Circuit source,
license and geometry prerequisites remain as documented in
[the workspace provenance notes](UPSTREAM_CIRCUIT_WORKSPACE.md).

## Reproduce

Build the hub and each series with the same production prefix used above. The
build environment for this audit is Node 20.20.2 and npm 10.9.9; dependencies
come from unchanged lockfiles. From the repository root:

```sh
node scripts/sync_shared_ui.mjs --check
node scripts/qa_theme_journeys.mjs /tmp/theme-journeys final
```

The browser runner uses the repository's Playwright package and
`/usr/bin/chromium`; its Node and Chromium versions are recorded in the report.
