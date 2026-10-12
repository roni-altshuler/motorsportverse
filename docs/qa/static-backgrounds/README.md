# Static backgrounds across MotorsportVerse

Base: `db06965c3631ecac1c7e7a7a6061e26f511b6bd0`.

The hub and all ten series sites now use stationary surfaces. The hub canvas,
loader, ambient store/control/boot script and body wash are removed. Decorative
hero circuit sweeps, breathing/floating hero layers, moving gradient text,
card/border/button effects, diagram flows, orbits and repeated marquees are
replaced by static rendering. Their callbacks, subscriptions and looping
keyframes are removed, rather than hidden or disabled only for reduced motion.
Historical component exports/props remain accepted for existing callers.

Ordinary focus/hover/press feedback, useful loading/freshness indicators, finite
entrances and user-operated circuit/replay/chart features remain. Circuit and
palette sources are byte-identical to base. Le Mans has no standalone website;
its hub listing and shared local circuit-workspace option remain available.

[Browser summary](browser-summary.json): **84 cases on 11 optimized exports**, at
1440×900 and 390×844, with normal motion preference and legacy ambient preference
set to `vivid`. There were zero decorative canvas paints, zero decorative infinite
animations, zero page errors and zero document-width overflows. **13 interaction
checks** passed: race filtering/search/selection, command palette, mobile menus,
and circuit snapshot stepping/driver selection. The circuit check uses the
existing clearly labelled fictional demonstration, not new race data.

[All 11 production exports passed](production-exports.json). Builds used current
pinned Next 16.3.8 with webpack and a process-local disk-cache override because
the saved environment is nearly full. Repository build configuration was not
changed; asset/data prebuild generators were not run. [Lint, types and full UI suites passed on all 11 apps](local-checks.json), including
**294 F1 tests**. The previous Singapore test failure was reproduced on the exact
base: mutable input had gained a result while the test still expected no result.
The authorized correction now uses immutable committed snapshots and tests both
held-forecast states, preserving exclusion and qualifying/grid assertions.
[Fixture provenance](../../../projects/f1-predictions/website/src/__tests__/fixtures/publication-hold/source-manifest.json)
records source commits and hashes; public inputs are unchanged. Static connectors
use actual endpoint coordinates so straight paths retain their colored stroke;
horizontal and vertical regression tests pass on all 11 apps. The browser probe
fails on document overflow. [Review corrections](review-corrections.json) include
real desktop/mobile About-page comparisons. The prior head's backend CI had 20
failures in unchanged model/data tests; this UI correction does not repair those
failures. New-head CI remains a separate required check.

**Theme limit:** current main hard-codes a dark palette and has no working light
palette/switch. Forcing `data-theme="light"` produces the same palette before and
after. Both requested attributes were checked; this is not a claim of functional
light-theme support. Color tokens were preserved. Existing external flag-image
failures are visible before and after, and remain outside this removal scope.

Before captures use the exact-base Next development server; after captures use
optimized static exports. Development chrome and live countdown times differ.
The captures are real pixels with running animations, not frozen/retouched images.

| Page | Before | After |
| --- | --- | --- |
| Hub desktop | [Screenshot](screenshots/before-hub-desktop-dark.png) | [Screenshot](screenshots/after-hub-desktop-dark.png) |
| F1 desktop | [Screenshot](screenshots/before-f1-desktop-dark.png) | [Screenshot](screenshots/after-f1-desktop-dark.png) |
| F2 mobile | [Screenshot](screenshots/before-f2-mobile-dark.png) | [Screenshot](screenshots/after-f2-mobile-dark.png) |
| F1 About desktop | [Screenshot](screenshots/before-f1-about-desktop.png) | [Screenshot](screenshots/after-f1-about-desktop.png) |
| F1 About mobile | [Screenshot](screenshots/before-f1-about-mobile.png) | [Screenshot](screenshots/after-f1-about-mobile.png) |

[Preservation](preservation.json) records unchanged public inputs, palette and
interaction files, plus all twelve previous local worktree heads. No laptop-only
work was transferred. No merge, deployment or production activation was performed.

To repeat an after-browser check after installing declared dependencies and
building an app's static export:

```sh
node docs/qa/static-backgrounds/browser-probe.cjs projects/f1-predictions/website
```

The probe serves that export only on loopback, checks the applicable routes,
records animations/pixels and tests the retained controls. Per-site JSON reports
include individual results. This evidence covers Chromium and local exports;
it does not claim a deployed CDN check or cross-browser coverage.
