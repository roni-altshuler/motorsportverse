# Shared circuit explorer preparation — 6 October 2026

**Held, unfinished draft. No Zandvoort map is approved or exposed by this change.**
The reusable shell is implemented and tested, but the saved cloud proxy returns
HTTP 403 for the supplied source PNG and official reference image. Normal,
explicit-network and execution-approval download paths did not recover either
file. Execution approval was accepted; this is a proxy response, not an automatic
approval rejection. Required source/reference cloud paths remain pending.

## Completed shell

The canonical `ui/CircuitExplorer.tsx` and `lib/circuitExplorer.ts` follow the
existing shared-copy/drift contract across all 11 sites. There are no production
consumer imports, registered reviews, source assets or new visible panels.
Existing telemetry outlines and the decorative F1 hero are unchanged.

- Explicit event matching checks series, season, round, venue, layout and date.
- A local manifest and PNG load only after user intent. A trusted manifest hash
  binds the exact descriptor bytes; identity, asset hash, complete credit, source
  revision, resize metadata and ordered corner coordinates are checked before display.
  The downloaded PNG must match its reviewed SHA-256 and byte count, have a PNG
  signature, decode successfully and match the declared dimensions. The shell
  renders those immutable blob bytes, never the mutable asset path.
  These checks establish descriptor integrity, not independent configuration or
  rights approval. A real source review is still necessary before registration.
- The shell supports three map buttons and a parallel corner list, arrow/Home/End
  navigation, selected-corner text, visible creator/source/license/modification
  credit and a non-endorsement notice.
- An optional six-second highlight tour pauses when less than 15% of the explorer
  is visible, when the document is hidden, and when closed. Reduced motion keeps
  manual controls and omits the automatic tour. No replay endpoint is used.
- Missing reviews render nothing. Checked claims, hotspots, corner lists and tour
  controls wait for the rendered image's load and dimension checks. An image error
  removes them and shows an explicit unavailable state with a **Try again** action;
  closing/reopening also retries. Closing, changing events, unmounting and pending
  decode cancellation release object URLs and discard late responses.

All test artwork and metadata live in `src/test-support/circuitExplorer.ts`, marked
synthetic QA only. They are not published assets or evidence for Zandvoort.

## Source dependency and intended pilot

The [Commons source page](https://commons.wikimedia.org/w/index.php?title=File:Zandvoort_Circuit.png&oldid=917222764)
identifies **Zandvoort Circuit.png** as Anthony Alessio Tralongo's own work under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), uploaded
31 January 2022 at 20:19 UTC. Its metadata reports 18,989 × 17,338 pixels,
4,143,465 bytes and SHA-1 `7815aff92487da7c125ea05278b3c251b758aee3`.
**That hash is source-reported, not computed from a local download here.**

Required files:

- [Original licensed PNG](https://upload.wikimedia.org/wikipedia/commons/7/78/Zandvoort_Circuit.png).
- [Official 2026 F1 verification reference](https://media.formula1.com/image/upload/c_lfill,w_3392/q_auto/v1740000001/fom-website/2026/Netherlands/2026trackzandvoortdetailed.webp).

The official reference is for comparison only and must not become the shipped
artwork. The parent researcher reported matching T1–T14 topology; this cloud
implementation has not independently inspected either image. No coordinates or
verification status are inferred from that report.

The [2026 F1 event page](https://www.formula1.com/en/racing/2026/netherlands)
and committed calendar identify **F1 2026 round 12, Zandvoort, 23 August,
4.259 km**. The [venue's corner page](https://www.circuitzandvoort.nl/en/corners/)
supports the intended three names: T1 Tarzanbocht, T3 Hugenholtzbocht and
T14 Arie Luyendykbocht. Other names, particularly T5–T7, remain unset.

To finish the bounded pilot:

1. Materialize the supplied PNG and reference in the saved cloud environment;
   inspect actual pixels, compute download hashes and compare T1–T14 topology,
   direction and the three hotspot positions.
2. Create a lightweight faithful PNG derivative, recording exact resize dimensions,
   algorithm, source revision, download hashes, output hash and comparison evidence.
   Preserve source attribution, modification notice, disclaimers and CC BY-SA 4.0
   for the derived map asset/annotations, separately from repository source code.
3. Register only the confirmed F1 event/configuration and integrate its launch
   surface. Do not relabel any FastF1 path. F2/F3 reuse remains unapproved until
   their configuration is independently checked; other sites gain no empty panels.
4. Run actual pilot browser QA: source rendering, touch/keyboard selection,
   visible credit, responsive layout, deferred requests, reduced motion and
   offscreen/hidden pauses. The schematic must not claim telemetry or survey accuracy,
   or invent speed, spatial DRS, sector, tyre-stint or replay information.

## Selection and keyboard focus — latest controlled browser evidence

The previous shell used F1's shadcn `--accent` alias as a selection signal. That
alias is dark `#1f1f1f`, and F1 has no `--accent-ink`. The new browser regression
first failed on head `ca8a0a66b5210412db3d87350058bb11be0e343d`, measuring the
expanded glyph at **1.12:1** against its background; see the
[expected pre-fix failure](contrast-before.log).

The explorer now uses supported **`--ink` / `--canvas`** values for the glyph,
inverted selected markers, selected list borders and keyboard focus. Both tokens
are explicitly present in all 11 copied sites. Global accents and token files
are unchanged. A canvas backdrop beneath a focused map button keeps the outline
legible over artwork. Scoped two-pixel focus utilities override F1's existing
unlayered one-pixel global focus rule; the browser checks their actual computed
width and style.

The **20 controlled Chromium image cases still pass**. Desktop/mobile success
cases additionally test collapsed/expanded glyphs, keyboard Tab navigation,
arrow-key transfer of selection/focus, matching map/list pressed states, selected
list focus and no horizontal overflow. Applying every site's real token CSS to
the shared fixture gives **22 computed palette checks**. Assertions require at
least 4.5:1 for glyph/marker text and 3:1 for selection/focus indicators.

| Computed pair | F1 desktop | Minimum across 11 palettes, desktop/mobile |
| --- | ---: | ---: |
| Expanded glyph / header | 18.42:1 | 17.61:1 |
| Selected marker text / fill | 21.00:1 | 18.54:1 |
| Selected / unselected marker fill | 18.42:1 | 17.61:1 |
| Selected list border / panel | 19.44:1 | 18.09:1 |
| Selected / ordinary list border | 15.13:1 | 14.02:1 |
| Focused map outline / canvas backdrop | 21.00:1 | 18.54:1 |

Four screenshots were visually inspected: the selected Turn 3 marker is inverted,
its matching row has a bright border, and keyboard focus is a separate two-pixel
outline on both map and list at desktop/mobile sizes. This is a styled local
synthetic fixture, not real-map approval or an audit of every production page.

After the final focus-width correction, **1,752 frontend tests passed**, with eight
existing hub skips; all **11 typechecks and static builds passed**. Relevant
component/browser-script lint, shared drift and diff checks passed. Native browser
QA records zero page errors, eight expected fault console errors and 20 created /
20 exactly matching revoked image URLs. The shell still has 45 shared regressions
per site; contrast assertions live in the controlled real-browser script.

See [latest browser report](contrast-browser-qa.json) and
[latest cross-site validation](contrast-validation.json). Screenshots:
[desktop marker focus](contrast-marker-desktop.png) ·
[mobile marker focus](contrast-marker-mobile.png) ·
[desktop list focus](contrast-list-desktop.png) ·
[mobile list focus](contrast-list-mobile.png).

## Image verification regressions and earlier browser evidence

The image-byte binding and decode gate address two independently reported shell
defects: a valid manifest previously allowed changed image bytes at its declared
path, and checked claims/controls could appear before the image actually rendered.

- **1,752 frontend tests passed**, eight existing hub skips; all **11 explicit
  typechecks and static builds passed** after the final image-binding changes.
  F1 used explicit `next build --webpack`; generic CI still skips its F1 build.
- **45 shared regressions per site** cover identity/provenance, actual image hash
  and byte count, dimensions, corrupt/non-PNG payloads, missing files, pending
  decode, rendered-image failure, changed rendered source, retry/reopen, event
  changes, stale responses and URL cleanup. jsdom decoder mocks are supplemented
  by actual native Chromium decoding below.
- **20 controlled Chromium cases passed**, ten cases at desktop 1440 × 1000 and
  mobile 390 × 844: valid, hash mismatch, dimensions, corrupt PNG, missing PNG,
  retry, reopen, rendered-image error, delayed decode and cancelled decode.
  The harness uses the current component/helper and built F1 styles, with a
  synthetic 12 × 9 checkerboard served only by a local controlled HTTP server.
  No product page or production review is registered. The report records **zero
  page errors**, **eight expected fault console errors**, and **20 created / 20
  revoked object URLs**, with exact URL matching and no duplicate revocations.
- Canonical component/helper, shared tests, synthetic support and browser-script
  lint pass. Shared drift and diff checks pass. The root lint invocation reports
  existing React/pages-directory configuration warnings; this is not a claim
  about whole-repository lint.

Reproduce after the F1 static build:

```bash
node scripts/qa_circuit_explorer_image.mjs /tmp/motorsport-explorer-image-browser
```

See [image verification cross-site validation](image-validation.json) and
[controlled browser report](image-browser-qa.json). Fixture screenshots:
[desktop success](image-fixture-valid-desktop.png) ·
[mobile success](image-fixture-valid-mobile.png) ·
[mobile unavailable/retry](image-fixture-missing-mobile.png).
These demonstrate shell rendering and fault handling, not real Zandvoort artwork,
source approval, configuration matching or delivered production explorer UX.

## Earlier preservation evidence

- **1,598 frontend tests passed**, eight existing hub skips; all **11 explicit
  typechecks and static builds passed**. The final intersection-threshold assertion
  was followed by another full test/typecheck run. Builds precede that small
  threshold alignment; the unused shell has no production bundle/HTML effect.
  F1 used explicit `next build --webpack`; generic CI still skips its F1 build.
- The initial shell had **31 meaningful shared regressions per site**. Canonical shell,
  guard, tests, synthetic support data and sync-script lint pass. Shared drift and
  diff checks pass. No claim about whole-repository lint is made.
- Actual static-export browser QA checked **four unchanged F1 hero cases**:
  desktop/mobile, normal/reduced motion, real stored Monaco path, existing CSS
  sweep behavior and zero replay requests. These are preservation checks, not
  Zandvoort or new-shell browser QA. The report records zero page errors,
  24 console errors and zero recorded HTTP resource failures. Existing image gaps
  remain visible in screenshots; this is not an error-free whole-site result.

The following reports predate the image verification fixes. See
[initial cross-site validation](validation.json), [initial final test/typecheck rerun](final-validation.json)
and [legacy hero browser report](legacy-hero-qa.json).

Legacy hero screenshots: [desktop](f1-hero-desktop-no-preference.png) ·
[mobile](f1-hero-mobile-no-preference.png).

PR11 merge ancestry and its local recovery branch are preserved. Its remote branch
was already removed with the exact reviewed-head lease. Main, model outputs,
published data, package/lockfiles and laptop-only unpublished work are unchanged.
No merge, manual workflow dispatch, new credentials, provider crawl or source
rights assumption occurred. The interactive explorer is not delivered.
