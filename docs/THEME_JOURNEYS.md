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
| Mobile navigation/layout | F1 closing drawer reached 710px in a 390px viewport; F1/MotoGP tab rows reached 395px; MotoGP header badges reached 406px | Remove closed mobile overlays immediately; wrap tab rows and bound the shared header action slot |

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
branding, chart tokens, data, models and accuracy claims remain unchanged.

## Browser verification

[`scripts/qa_theme_journeys.mjs`](../scripts/qa_theme_journeys.mjs) serves actual
static exports at `/motorsportverse` and `/motorsportverse/projects/<series>`.
It clicks the hub directory, project details and existing Live demo links,
substituting only each launch link's origin with the local server. It follows
actual site links through calendar, an available race detail, standings,
available driver/rider/entry profile, accuracy/evidence, back, forward, reload and about.
F1's profile is reached through its actual **Drivers** navigation link; MotoGP
uses the actual **`/rider/`** links in its standings. The other six series with
profiles use their existing `/driver/` links. WEC and IMSA use their actual
`/round/` calendar details and `/entry/` standings profiles. Their earlier
"unavailable" statement was a runner path-family error, not missing data.

Each normal-route measurement requires the explicit intended path and that
destination's own expected heading/content. Static identities come from the
corresponding production export; race, standings and driver/rider identities
come from the stored series JSON. A matching URL or an existing layout `main`
alone cannot pass. Local browser fetches must finish, visible loading indicators
must disappear, fonts must settle, and destination-heading geometry/page width
must agree across three consecutive rendered frames (0.5px geometry tolerance
for browser subpixel layout). The primary heading must be
visible, with its opacity and rendered geometry settled after any entrance
animation. The runner scrolls that real heading into view, including F1's
accuracy title below its evidence section. There is no fixed route-measurement
sleep. Native browser time and animation timelines are used: the previous
Playwright clock override produced animation-settling failures on reload in the
isolated probe, while the same fresh/reloaded route passed with native time.
The report records expected and observed headings, pending fetch/loading counts
and settled frames for every appearance sample. Deliberate loading fixtures are
explicitly marked and are the only samples allowed to retain pending/loading UI.

Independent review identified that the initial runner used a URL plus `main`
and a 100ms delay, and missed F1/MotoGP profiles and WEC/IMSA round/entry paths. The final report was
replaced by the stronger rerun. Five actual Chromium regressions separately
prove that previous-route content, a pending local data fetch and a visible
loading indicator, hidden primary heading or moving heading prevent measurement,
then pass when the condition is resolved.

Mobile journeys click within the actual menu and assert that it unmounts,
rather than selecting a visible header/footer link behind an open menu.
Navigation scrolls the actual browser viewport to the top. Link clicks use native
pointer input only after a DOM hit test proves the actual link is unobstructed;
no forced click bypasses an overlay. This tolerates harmless navbar subpixel
movement while still requiring the requested destination and closed menu.

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
- [Intermediate mobile overflow probe](qa/theme-journeys/mobile-layout-before.json)
- [Series recovery baseline](qa/theme-journeys/series-recovery-before.json)
- [Baseline production-path builds](qa/theme-journeys/baseline-builds.json)
- [Final browser report](qa/theme-journeys/after.json)
- [Final local check matrix](qa/theme-journeys/local-checks.json)

The final Chromium 151.0.7922.173 run passed all four cases: desktop 1440×1000
and mobile 390×844, each with light and dark system color preferences. Light
cases used reduced motion; dark cases used normal motion. This is four cases,
not a full cross-product of every motion and color preference. The browser
runner used Node 24.19.0; builds/checks used Node 20.20.2 and npm 10.9.9.
The cases ran independently against identical runner, readiness-helper and
product-source hashes; their complete records were combined into `after.json`.
All ten series exercised actual detail and profile routes in each case:
**40 race/round-detail visits and 40 driver/rider/entry-profile visits**.

All 103 recorded product source hashes, the runner hash and the readiness-helper
hash match the tested files. There were zero failed journey assertions, browser
errors or unexpected local HTTP failures. Actual 404s and route recovery fixtures now have one main
landmark. All mobile menus unmount after their real menu links are clicked.
The saved ambient preference remains off through navigation, history and hard
reload, and first styled canvases match the hydrated canvases. All series keep
their original palette/body font along the tested routes.

Solid launch labels now measure **4.85–14.24:1** across the ten actual accents.
F2, F3, NASCAR and WEC measure **6.38, 8.86, 14.24 and 11.27:1**. The hub small
caption measures **6.48:1**, its focus outline **5.16:1**, and its root diagnostic
ink **6.48:1**. Series root diagnostic ink measures **5.32:1**. The final mobile
circuit capture is **390px** wide; the intermediate overflowing capture was
**710px** wide.

All eleven frontend suites passed lint, tests, types and production-path static
builds: **44 checks**, **2,060 passed tests**, **eight existing hub skips** and
unchanged lockfiles. Shared UI drift and whitespace checks passed. Root/F1
Ruff 0.8.6 checks passed; root CI separately pins 0.16.1. The offline coverage
suite passed all 14 tests, and F1 schema/workflow regressions passed with one
explicit skip. No new clean local install is claimed; CI performs locked installs.

Screenshots are actual browser captures. The hub recovery images use the
explicit actual-markup style fixture described above:

| Before | After |
| --- | --- |
| [Hub recovery](qa/theme-journeys/hub-recovery-before.png) | [Hub recovery](qa/theme-journeys/hub-recovery-after.png) |
| [Mobile circuit overflow](qa/theme-journeys/mobile-circuit-before.png) | [Mobile circuit workspace](qa/theme-journeys/mobile-circuit-after.png) |

Also see the [actual hub 404](qa/theme-journeys/hub-404-after.png) and
[mobile NASCAR launch](qa/theme-journeys/mobile-launch-after.png), plus the
confirmed [F1 driver viewport](qa/theme-journeys/f1-profile-after.png) and
[MotoGP rider viewport](qa/theme-journeys/motogp-profile-after.png).

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
node --test scripts/lib/route_readiness.test.mjs
node scripts/qa_theme_journeys.mjs /tmp/theme-journeys final
```

The browser runner uses the repository's Playwright package and
`/usr/bin/chromium`; its Node and Chromium versions are recorded in the report.
