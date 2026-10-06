# Published result coverage — 6 October 2026

The bounded fix separates **no ingestible update detected** from **published
results cover the calendar**. F2/F3/IndyCar's boolean live gate returns false on
source initialization/fetch/parse failures. Previously this skipped refresh and
validation and printed “Nothing new to publish”. Passing corpus checks or a new
export timestamp cannot establish current result coverage.

## Verified coverage and official availability

All three published summaries were exported on **16 August 2026**. As of
6 October, their committed calendars and imported-result flags imply:

| Series | Imported weekends | Past-due, unimported rounds | Official free evidence |
| --- | --- | --- | --- |
| F2 | 6 / 14 | R7–R12 (six) | [2026 official calendar and session winners](https://www.fiaformula2.com/en/racing/2026) shows results for Silverstone, Spa, Budapest, Monza, Madrid and Baku; Lusail and Yas Marina remain upcoming. [Baku classification](https://www.fiaformula2.com/en/racing/2026/baku) confirms Feature Race 2 results. |
| F3 | 5 / 9 | R6–R9 (four) | [2026 official calendar and session winners](https://www.fiaformula3.com/en/racing/2026) shows results for Spa, Budapest, Monza and Madrid. [Madrid classification](https://www.fiaformula3.com/en/racing/2026/madrid) confirms Feature Race 2 results. |
| IndyCar | 11 / 18 | R12–R18 (seven) | [Official schedule](https://www.indycar.com/Schedule) shows winners/recaps for Nashville, Portland, Markham, Washington, both Milwaukee events and Laguna Seca. The [official results page](https://www.indycar.com/results/ntt-indycar-series/2026/mission-foods-grand-prix-of-monterey/race) is dynamic; its full classification was not verified via the text reader. |

These are **weekend/round coverage counts**, not session totals. Availability of
official results on the website is different from their being accepted by the
repository's existing ingestion adapter. No classifications were copied, no
snapshot/export was regenerated, and no completion flag was inferred from time.

The configured legacy FIA anchors
[`/Results?raceid=1092`](https://www.fiaformula2.com/Results?raceid=1092) and
[`/Results?raceid=1069`](https://www.fiaformula3.com/Results?raceid=1069) returned
404 through the web reader. Shell requests to these domains were blocked by the
environment proxy with 403, so live adapter operation was not verified here.
The modern official pages above remained readable via the web tool.

Ingestion repair needs separate verification: Baku F2 and Madrid F3 expose
**Sprint + Feature Race 1 + Feature Race 2**, while the repository models a single
feature session. IndyCar's official schedule gives Nashville as **20 July**
(committed: 19 July) and both Milwaukee events on **30 August** (committed:
29/30 August); the official listing's R1/R2 order needs explicit reconciliation.
Do not bypass wrong-event guards or relabel a result to force ingestion.

## Behavior

- `python scripts/check_result_coverage.py f2` (also `f3`, `indycar`) reads only
  committed published summaries. It checks **every** calendar round, including
  gaps before later imports. A scheduled UTC race day gets its full day plus
  **48 hours** before coverage becomes past due. This is an operational grace
  policy, not a claim about when official results should publish.
- Exit **0** means no past-due calendar gaps, **1** means past-due or unknown-date
  coverage, **2** means the dataset could not be read/validated. Source
  availability is always reported as **not checked**. `--as-of` and `--data`
  make audits reproducible without network requests.
- Each affected poll has a separate `coverage` job with `needs: predict` and
  `if: always()`. It checks the branch after the prediction job (including any
  newly committed results), writes a step summary and fails visibly for gaps
  even after a no-work poll. The deploy job still depends only on `predict`, so
  this observational audit does not block publishing valid incremental results.
- The homepage shows imported/total rounds, latest imported result, export date,
  and expandable past-due round links. It distinguishes calendar coverage from
  source availability. The client rechecks at hydration and hourly so static
  exports do not freeze the date comparison. An old forecast is labelled
  **Past-due forecast** instead of **Next up**. Unimported race details say
  **Snapshot Forecast**, avoiding an unsupported “Upcoming” claim.
- The forecast badge and homepage carousel now use the same hydration/hourly
  clock and grace policy as the coverage panel. During the saved race day and
  grace period they say **Snapshot forecast**; after grace they say **Past-due
  forecast**. Only dates still ahead can say **Next up** or **Upcoming**. Missing
  or invalid dates stay snapshot forecasts. The standalone countdown says
  **Scheduled date passed** after its target rather than “this weekend” forever.
- No model, probability, production job, repository visibility, main branch, or
  laptop-only unpublished navigation branch was changed. This work exists only
  in the saved cloud checkout and its draft PR.

## Validation

- Python: **400 passed** across shared core/data, F2 and the audit tests (including
  **14** audit regressions). Tests reproduce failed live gates returning no work
  for all three series while the independent audit reports a known gap.
- Published-data integrity: **115 checks passed** across the three datasets.
  Separately, the new coverage audit correctly exits **1** for all three with
  the six/four/seven overdue counts above; it does not claim the data was fixed.
- F2/F3/IndyCar: **79 / 75 / 75** frontend tests, typechecks, changed-file ESLint and production
  static builds were run. `next lint` is unavailable in Next 16; direct ESLint
  used the installed Next core-web-vitals and TypeScript configs.
- Shared-UI drift and workflow YAML parsing passed. Dependency declarations and
  lockfiles were preserved; IndyCar used the existing lockfile-preserving install
  workaround because its lock omits declared development dependencies.
- Browser QA: `node scripts/qa_result_coverage.mjs` serves the three actual static
  exports, uses system Chromium, and checks desktop/mobile panel text, keyboard
  disclosure, all gap links, race navigation/back/forward, console/page errors and horizontal
  overflow; resource/framework errors are recorded rather than suppressed. The screenshot clock is fixed to 6 October 2026 for reproducibility.
  See `browser-qa.json` and the screenshots in this directory for the final run.
- WRC: **36 tests passed**, including five additional boundary/payload cases.
- Aggregate checks: **407 corpus checks** and registry/shared-UI/palette checks
  passed. All **10 evidence artifacts** match under CI's Python **3.11**.
  Python 3.12's changed floating-point summation rounds one MotoGP baseline mean
  differently at the sixth decimal; regenerating with 3.11 reproduced the
  committed file exactly. No MotoGP artifact, evaluation or evidence gate changed.

Screenshots: [F2 desktop](f2-desktop.png) · [F2 mobile](f2-mobile.png) ·
[F3 desktop](f3-desktop.png) · [F3 mobile](f3-mobile.png) ·
[IndyCar desktop](indycar-desktop.png) · [IndyCar mobile](indycar-mobile.png).

### Browser limitations

The functional coverage/navigation assertions passed at both viewport sizes,
but this is **not an error-free browser run**. All three sites emitted React
hydration error #418 and failed image requests (blocked remote images and/or
missing local headshots). Isolated builds of all three sites at the unchanged base commit
`01406e54f42b413299246da67ad64a849b649f22` reproduced the same hydration error
under the same browser clock. See `baseline-comparison.json`. The new panel
renders and hydrates with a serialized initial timestamp; its unit tests also
exercise a static export aging after hydration. Broader existing homepage
hydration and asset repair remain separate work.

### Bounded visual treatment and browser fixtures

The coverage callout keeps the original series typography and dark theme, uses
neutral surfaces, a purposeful warning rail, readable labels, native keyboard
disclosure and clearly named round links. It adds no white light surface or new
decorative animation. Focus states use existing tokens and browser QA uses
reduced motion.

An isolated temporary F2 build rendered the **exact new component** in an empty
calendar state, an unknown-date state, and a future scheduled-round state. All
three states passed desktop and mobile browser assertions without page errors
or overflow (`fixture-browser-qa.json`). The temporary QA route was never added
to the repository or the published site; its events are explicitly QA fixtures,
not results. Empty coverage shows “No result coverage published” and an em dash
instead of implying zero verified coverage. The component reads a static
snapshot synchronously, so it has no network-loading state; the initial server
render and post-hydration time recheck are covered.

Fixture screenshots: [empty mobile](empty-mobile.png), [unknown mobile](unknown-mobile.png),
[future desktop](future-desktop.png). Every state also has desktop/mobile captures
in this directory.

The revised isolated build also uses an explicitly old serialized build time.
Both viewports verified that hydration brings the panel, forecast badge and
carousel into agreement, and advancing the browser clock across the 48-hour
grace boundary changes all three together. These fixtures emitted **zero page
errors**. See [aged mobile](aged-mobile.png), [aged desktop](aged-desktop.png) and
the updated `fixture-browser-qa.json`. The actual homepages' carousel labels
were checked at both sizes too; see [F2 mobile](f2-carousel-mobile.png),
[F3 mobile](f3-carousel-mobile.png), [IndyCar mobile](indycar-carousel-mobile.png).
Mobile cards reserve space for wrapped photo credits. Browser geometry checks
confirm that forecast captions do not overlap those credits.

### Independent-review correction: WRC final-round boundary

The [official WRC calendar](https://www.wrc.com/en/calendar) lists **13 rounds**,
ending with Sardegna on **1–4 October 2026**. The
[FIA event review](https://www.fia.com/news/2026-fia-world-rally-championship-rally-italia-sardegna-event-review)
explicitly identifies it as the season finale. The saved WRC calendar,
`totalRounds`, completion list and result blocks all cover R1–R13; its published
summary has `nextPrediction: null`. The preexisting test nevertheless tried to
read `round_14.json` when `COMPLETED_ROUNDS == 13`.

The correction checks actuals/accuracy for **every scheduled completed round**
and their absence for every pending round. A completed season must have no next
prediction and no extra round file. Additional cases retain pending-payload
checks even when the real saved season is complete, and exercise not-started,
final-round-pending and complete calendar boundaries. No WRC source, calendar,
result, configuration or model was changed; no extra round was invented.

Preexisting calendar/navigation/live-context labels elsewhere still derive
“next” from imported-round order. This bounded change fixes the reviewed
homepage coverage/forecast/carousel path; broader navigation chronology remains
follow-up work.
