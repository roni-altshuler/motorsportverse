# F1 held-race overview

Base: `fd1f6104939665dc1e807e6ce1ea484f82b11afc`.

Publication-held F1 rounds now lead with the recorded race leaders, event and
compact forecast/baseline status. Observed positions come from `actualResults`;
the sealed grid baseline remains a separate pre-race record. Singapore's model
forecast stays withheld and excluded from accuracy. Its recorded third-place
finisher and the baseline's third-place pick remain distinct.

The existing baseline and publication-review panels are retained inside native,
initially closed disclosures. Their sources, seal timestamps, original forecast
record and qualifying-versus-final-grid distinction are unchanged. The full
race-result session precedes other sessions when a result is recorded. Driver
links open existing profiles; Explore Circuit opens the existing workspace.

[Validation](validation.json): 300 UI tests across 23 suites, types and optimized
production build pass. Lint has zero errors and one warning in an unchanged
accuracy-page file. No models, public data, guard helpers, palettes or shared
background components changed. Thirteen prior worktrees are preserved.

[Development QA](development-qa.json) and [optimized-export QA](production-qa.json)
each pass ten Chromium cases. Coverage includes 1440×900, 390×844 and 320×780,
keyboard open/close cycles, visible focus, full-result anchor positioning,
profile/circuit navigation, repeated/interrupted race navigation, delayed data,
HTTP failure, invalid JSON, a historical no-result snapshot and off-calendar
navigation. There are no page errors or document-width overflows in those checks.
The simulated responses use immutable existing fixtures or explicit transport
failures; they do not claim current official results are missing.

| View | Before, development | After, same development mode | Optimized export |
| --- | --- | --- | --- |
| Desktop | [Pixels](screenshots/before-desktop.png) | [Pixels](screenshots/after-desktop.png) | [Pixels](screenshots/production-desktop.png) |
| Mobile | [Pixels](screenshots/before-mobile.png) | [Pixels](screenshots/after-mobile.png) | [Pixels](screenshots/production-mobile.png) |
| Narrow | [Pixels](screenshots/before-narrow.png) | [Pixels](screenshots/after-narrow.png) | [Pixels](screenshots/production-narrow.png) |

On mobile, recorded leaders begin at approximately 363 px; the full result table
moves from 8,367 px to 1,010 px. These are measurements of this saved input and
viewport, not performance or model-quality claims. Captures use normal motion,
with fonts and ordinary rendering allowed to settle; pixels are not retouched.
Live countdown values and development chrome differ across capture times/modes.

Limits: Chromium and local exports only; no hosted or cross-browser claim. The
existing palette is dark-only. Existing external flag-image failures remain.
The nearly full environment used a private Next 16.3.8 runtime with source maps
omitted; executable JavaScript/native code and repository configuration stayed
unchanged. A process-local build-cache override avoided writing cache files;
asset/data prebuild generators were not run.

To repeat after installing declared dependencies, start the app or serve its
static export, then run:

```sh
node docs/qa/f1-compact-overview/browser-qa.cjs http://127.0.0.1:3361 development
```
