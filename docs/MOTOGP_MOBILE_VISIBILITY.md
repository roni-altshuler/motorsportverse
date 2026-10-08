# MotoGP mobile visibility review

The cloud browser reproduces visible race content after real scrolling on both
exact base `b9408e3a56bd08e51220709aae5f017dabcda272` and application head
`57338024e3ac5725f5c84d0c3fd839d8ec1cf85f`. No application regression was
reproduced. This follow-up changes browser QA and evidence only.

The earlier series checks asserted a heading/status and captured a full page;
they did not check the race body's actual opacity or scroll through every
section. The shared browser runner now checks MotoGP's podium, probability
board and entire classification on desktop and mobile. Other series retain
their existing checks; this is not a claim of expanded body coverage for them.

## Matched browser verification

[The saved runner](../scripts/qa_motogp_mobile_visibility.mjs) serves the two
actual static exports in Chromium 151.0.7922.173, with identical 390 × 844
viewports, route `/race/1/`, browser date and scroll sequence. It runs both
`reduce` and `no-preference` motion settings: **four matched cases**.
It verifies **229 base source/public/build-input files** byte for byte against
Git and verifies each export's round JSON against its committed source.
The base uses a separate physical install of the repaired head dependency lock
because its original lock fails `npm ci`; dependency declarations are unchanged.
It is an exact base application-source comparison, not an original-lock build.

Each case passes **48 painted-content assertions**: the podium heading and all
three names/cards, probability board and all 12 driver rows, and all 31
classification rows. These inspect ancestor opacity/display/visibility, box
dimensions, viewport intersection and hit testing, alongside published driver
identities. All four cases pass, totaling **192 assertions**, with zero page
exceptions. Seven section captures per case also verify that the content is
uncovered below the real sticky header. No CSS is hidden for capture.

After capturing real content, a separately marked **QA-only negative fixture**
sets the probability panel's opacity to zero. Its heading remains in the DOM,
but the new guard rejects the hidden body. The runner restores its original
style and verifies visibility again. No source/exported race data is changed.

Both exports share round JSON SHA-256
`e7d3245fcc36d33f412dd14a76891d0da92c34cb0d2b12eb967a97ba348f96de`,
scroll stops and document dimensions **406 × 6460**. The inherited 16px
horizontal overflow at a 390px viewport remains. Missing portrait requests are
retained and verified absent on the base; any other failed local resource fails
the runner. These checks certify visibility of the committed page, not the
official status or accuracy of its race data or model.

Run after building the head site and an adjacent-source exact base snapshot:

```sh
node scripts/qa_motogp_mobile_visibility.mjs /path/to/base-website/out /tmp/motogp-visibility
node scripts/qa_lint_repair.mjs /tmp/motorsport-browser-qa
```

The rerun of all **18 existing browser flows** also passes, with zero page
exceptions. It records 173 inherited portrait-404 events, rather than the
earlier 102: scrolling the MotoGP body loads more lazy portraits. These counts
are observations of each run, not unique missing files.

## Evidence discrepancy and readable captures

The two original PNGs at application head `5733802` have the same Git blob,
`9221f620b2a1de1b34b73551be32c52fcc8541c5`, and **zero differing pixels**.
The perceived preview discrepancy is not present in those stored bitmaps.
The stronger browser checks above address the independent QA gap regardless.

All seven new reduced-motion section pairs are pixel-identical. Normal-motion
probability and classification section pairs are also identical; some podium
and full-page pixels differ during ongoing counters/decorative animations.
Full pages are not claimed to be byte-identical. The complete numerical pixel
comparison is retained, including those differences.

| Section | Exact base | Application head |
| --- | --- | --- |
| Probability board | [Base](qa/lint-repair/motogp-visibility/base-reduce-probabilities.png) | [Head](qa/lint-repair/motogp-visibility/head-reduce-probabilities.png) |
| Winner card | [Base](qa/lint-repair/motogp-visibility/base-reduce-podium-BEZ.png) | [Head](qa/lint-repair/motogp-visibility/head-reduce-podium-BEZ.png) |
| Last classification row | [Base](qa/lint-repair/motogp-visibility/base-reduce-classification-30.png) | [Head](qa/lint-repair/motogp-visibility/head-reduce-classification-30.png) |
| Scrolled full page, reduced motion | [Base](qa/lint-repair/motogp-visibility/base-reduce-full.png) | [Head](qa/lint-repair/motogp-visibility/head-reduce-full.png) |
| Scrolled full page, normal motion | [Base](qa/lint-repair/motogp-visibility/base-no-preference-full.png) | [Head](qa/lint-repair/motogp-visibility/head-no-preference-full.png) |

[Matched four-case report](qa/lint-repair/motogp-visibility/matched-browser-qa.json),
[pixel comparison](qa/lint-repair/motogp-visibility/pixel-comparison.json), and
[18-flow rerun](qa/lint-repair/motogp-visibility/all-flows-browser-qa.json).
The application tested is `5733802`; the subsequent evidence commit modifies
only these QA scripts, documentation and captures. PR #13 remains draft for
independent review. Main and held PR #12 are preserved.
