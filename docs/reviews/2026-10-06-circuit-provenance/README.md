# Circuit identity guard revision — 6 October 2026

The requested interactive **Explore circuit** feature remains **unfinished**.
This revision separates legacy display from new explorer approval. Missing review
records no longer strip all F1/F2/F3 geometry or the decorative F1 ribbon.
**43 stored paths / 168 calendar rounds; 37 legacy outlines retained; zero
explorer-reviewed layouts.** See [coverage and prerequisites](../../CIRCUIT_GEOMETRY.md)
and the [read-only inventory](coverage-audit.json).

Confirmed Austria/Silverstone conflicts remain quarantined without relabelling
which venue is correct. Hungaroring retains its outline and 12 unambiguous markers;
only repeated numbers 1/12 are suppressed, without invented suffixes. The generator
drops FastF1's Letter field, so duplicate numbers do not establish a wrong outline.
The generic F1 fallback is removed. Other sites' loaders/presentation stay unchanged;
there are no new empty explorer panels. No raw data, package/lockfiles or replay
behavior changed.

## Validation

- At prior head `43930c8`, **1,253 frontend tests passed**, eight existing hub skips; all **11 explicit
  typechecks and static builds passed**. F1's actual static export was built with
  `next build --webpack`, bypassing its unrelated image-generation prebuild.
  The generic frontend CI still skips F1's build; a CI test pass is not a claim
  that it ran that build. See [validation](validation.json).
- New guard/component/tests, F1 loader/RaceDetail and touched F2/F3 loader/panel
  ESLint passed using the existing F1 config. The unchanged full F2/F3 RaceDetail
  archival-overlay effects retain their preexisting hook-lint errors. Both were
  reproduced from `43930c8` during the copy correction. No clean
  whole-site lint claim is made.
- Shared-copy drift, diff checks and all **407 published-corpus checks passed**.
  The report-only inventory separates legacy outline, corner and explorer states;
  `--require-verified` still correctly exits 1 for current explorer coverage.

## Browser evidence

The 64-race and four-hero reports below were recorded at prior head `43930c8`.
The narrow copy correction has separate current evidence below; it changes no
geometry or hero behavior.

`node scripts/qa_circuit_geometry.mjs <output-dir>` serves actual static exports
with system Chromium and the installed Playwright. It checks **64 actual race
cases** (F1/F2/F3, 1440/390 pixels, normal/reduced motion): quarantined maps,
positive Monaco/Australia maps, retained Hungaroring outlines with ambiguous
markers suppressed, and F2's missing Miami map. Existing F2/F3 native disclosures
are checked by keyboard through open/close/reopen. No map clipping or horizontal
overflow was observed in these cases, and no replay requests were made.

A separate `--hero-only` browser run checks **four positive F1 home cases**,
selecting the real Monaco event with an advancing clock starting 5 June 2026. The headline is visible and the ribbon
path equals the actual stored Monaco path. CSS dash offset moves under the 14s
infinite sweep with normal motion; reduced motion keeps the ribbon present with
one near-zero-duration iteration and a stable dash offset. The wall clock advances while native animation timing stays intact. Finite
headline entrance animations settle before screenshots. This preserves existing motion, without claiming to fix offscreen behavior or deliver an explorer.

Hero screenshots:
[desktop normal](f1-hero-desktop-no-preference.png) ·
[desktop reduced](f1-hero-desktop-reduce.png) ·
[mobile normal](f1-hero-mobile-no-preference.png) ·
[mobile reduced](f1-hero-mobile-reduce.png).

Preserved map screenshots:
[F1 desktop](f1-preserved-desktop.png) · [F1 mobile](f1-preserved-mobile.png) ·
[F2 desktop](f2-preserved-desktop.png) · [F2 mobile](f2-preserved-mobile.png) ·
[F3 desktop](f3-preserved-desktop.png) · [F3 mobile](f3-preserved-mobile.png).

Quarantine screenshots:
[F1 desktop](f1-desktop.png) · [F1 mobile](f1-mobile.png) ·
[F2 desktop](f2-desktop.png) · [F2 mobile](f2-mobile.png) ·
[F3 desktop](f3-desktop.png) · [F3 mobile](f3-mobile.png).

The [race report](browser-qa.json) and [separate hero report](hero-qa.json) retain
console/page errors and failed
resources. Asset failures remain recorded; prior F2/F3 hydration #418 is documented at
baseline. This is not a clean whole-site browser result. [The prior baseline comparison](../2026-10-06-result-coverage/baseline-comparison.json)
records F2/F3 hydration at the unchanged base. The [initial-guard comparison](baseline-comparison.json)
is explicitly historical at fb922e2, not evidence for the revised hero.

## Review-copy correction

F2/F3 previously claimed that only a verified layout could appear below retained
maps labelled "Layout review pending". The disclosure now distinguishes existing
outlines awaiting review from the unavailable interactive explorer, which requires
a reviewed layout. Quarantined or missing maps explicitly say no outline is
available for that event.

Both actual RaceDetail components have rendered-text regressions using saved Monaco
and Silverstone data. The four new assertions fail against the original copy.
The affected full suites pass **130 F2 tests and 126 F3 tests**, with both explicit
typechecks and static builds passing. New test and QA-script lint, shared-copy
drift and diff checks pass. The only full-component lint failures are the existing
archival-overlay effect errors described above. See [copy validation](copy-validation.json).

`node scripts/qa_circuit_geometry.mjs <output-dir> --copy-only` checks **eight actual
static-export race cases**: retained Monaco and quarantined Silverstone in F2/F3,
desktop/mobile with reduced motion. It checks the entire disclosure's visible text,
absence of verification claims, keyboard open/close/reopen, overflow and zero replay
requests. All assertions pass, with zero page errors. The [copy report](copy-browser-qa.json)
retains 258 console errors and 250 asset failures; this is not a clean whole-site
browser result. Screenshots include the text below the map, which older panel-only
captures omitted:

- Retained F2: [desktop](f2-retained-copy-desktop.png) · [mobile](f2-retained-copy-mobile.png).
- Retained F3: [desktop](f3-retained-copy-desktop.png) · [mobile](f3-retained-copy-mobile.png).
- Unavailable F2: [desktop](f2-unavailable-copy-desktop.png) · [mobile](f2-unavailable-copy-mobile.png).
- Unavailable F3: [desktop](f3-unavailable-copy-desktop.png) · [mobile](f3-unavailable-copy-mobile.png).

## Scope and next prerequisite

Monaco is the first candidate: identical existing F1/F2/F3 paths and 19 unique
markers, with official 2026 venue/length facts. A viewable current layout reference,
source-appropriate provenance and documented reuse basis are still required;
older freely licensed diagrams do not approve our telemetry path. Geographic
sources need a pinned revision, not a timed session. No layout is approved here.

PR10 merge ancestry/local recovery, main and laptop-only work are preserved.
No merge, production dispatch, provider crawl, new credentials, model change or
laptop branch transfer occurred. This remains a draft for independent review.
