# Circuit workspace verification — 8 October 2026

The new F1 `/circuits` route is an original browser-local consumer of Tom Shaw's
inspected stream format. All inputs used here are **original synthetic messages**.
The oval, square and named drivers are fictional QA data. This evidence does not
verify a real circuit, historical race or running upstream producer.

[Implementation and source audit](../../UPSTREAM_CIRCUIT_WORKSPACE.md) ·
[checks](checks.json) · [browser report](browser-qa.json) ·
[F1 Python output](f1-pytest.log).

## Checks

- Clean locked installs, lint, full frontend tests, TypeScript and static exports
  pass across all 11 sites under Node 20.20.2 / npm 10.9.9. Locks are unchanged.
  The final suites contain **2,016 passing tests and eight existing hub skips**.
- F1's actual production-path export uses `/motorsportverse/projects/f1`.
- F1 Ruff 0.8.6 passes. Its full Python suite passes **1,087 tests with two skips**
  in the local Python 3.12.14 environment. CI separately uses its configured
  Python 3.11 environment. No model promotion or production pipeline was run.
- Shared-copy drift, script syntax and whitespace checks pass. Browser source
  hashes bind the inspected files; `checks.json` records the export build ID.

## Actual browser checks

System Chromium runs the exported site at 1440×1000 and 390×844 with both motion
preferences. Each case checks all 11 series' unavailable state; keyboard menu
entry; native slider and driver activation with a visible focus ring; 18 repeated
driver selections; manual reset/seek/step; same-file reopening; missing geometry,
missing positions and preserved rewinds; error recovery; cancelled late reads;
series clearing; empty reload; and two event-link navigation cycles.

The only test injection delays browser-local `File.text()` to expose loading and
cancellation. No source assets, API responses, layout registry, motion preference
or upstream process are substituted. Snapshot positions stay unchanged until
input. Imported data produces no upload requests; read-only framework prefetches
and cancelled framework HEAD probes are retained in the report.

All four cases pass with zero page exceptions, zero failed local HTTP resources
and no horizontal overflow. Existing external flag-image tunnel failures remain
visible in the console/network evidence and screenshots. This is not an
error-free whole-site claim or a public deployment verification.

Screenshots were visually inspected. They are captured after a real upward wheel
gesture settles the site's native/smooth-scroll positions, preserving the header
and keyboard selection state:

| State | Screenshot |
| --- | --- |
| Desktop unavailable | [1440px, reduced motion](desktop-reduce-unavailable.png) |
| Mobile unavailable | [390px, reduced motion](mobile-reduce-unavailable.png) |
| Fictional demo / keyboard selection | [desktop](desktop-no-preference-demo-keyboard.png) · [mobile](mobile-reduce-demo-keyboard.png) |
| Synthetic local-file import | [desktop](desktop-no-preference-local-fixture.png) · [mobile](mobile-no-preference-local-fixture.png) |
| Pending read / cancellation | [mobile, normal motion](mobile-no-preference-loading.png) |
| Invalid JSON / recovery | [mobile, normal motion](mobile-no-preference-error.png) |

## Remaining limits

Actual upstream code copying requires complete license terms; the inspected
README's MIT claim is not backed by a LICENSE file. No upstream code was copied.
Real-file producer interoperability remains unverified without a lawfully
obtained capture. The licensed original Zandvoort PNG and official configuration
reference remain unavailable through the saved cloud path. No layout review is
registered; this demonstration does not complete the real-map pilot.

The existing draft PR #12 is reused for independent review. Main, the decorative
hero, quarantines, licensed artwork, published data and laptop-only work are
preserved. No merge or production job dispatch.
