# Singapore official-grid baseline display

This independent forecast uses the verified final starting grid as its finish
order. Its winner pick is Max Verstappen; it assigns no win probability and
does not model weather, strategy or retirements. The advanced model forecast
remains withdrawn, with the original quarantine and publication hold intact.

## Immutable record and sources

The existing baseline was sealed at **2026-10-11 06:53:07.672909 UTC**, before
the verified 12:00 UTC race start. Its bytes are copied unchanged to
`website/public/data/baselines/2026_round_17_f994d9796f18.json`.

SHA256: `f994d9796f18458398c2733e48ab27a984cff51aa57874323d1aa61f6cde0c58`.

The official pages were rechecked at **07:09:02 UTC** before staging. All 22
grid positions still match the seal. Qualifying is shown separately: Russell
qualified sixth and starts 21st after a 40-place power-unit penalty.

- [Official post-penalty starting grid](https://www.formula1.com/en/results/2026/races/1296/singapore/starting-grid)
- [Official qualifying](https://www.formula1.com/en/results/2026/races/1296/singapore/qualifying)
- [Official event schedule](https://www.formula1.com/en/racing/2026/singapore)
- [Bounded source comparison and all positions](source-verification.json)

The receipt `website/public/data/baselines/2026_round_17.json` separates the
original seal, later source check and review-branch staging time. Staging is
not claimed as the first public display time. Source commit `5e2aa476…` and
the original round/season byte hashes identify the exact factual snapshots;
those snapshots are unchanged on the newer main base `72d808e9…`.

The seal pins policy and generator hashes. [The sealing implementation
snapshot](sealing-implementation.txt) and [the staging implementation snapshot](staging-implementation.txt)
preserve the exact bytes used at those times. The maintained staging helper
has the same behavior with a typed position-map helper; the receipt continues
to name its original staging snapshot, not a later source version.

Original source-extraction bytes remain in the saved-cloud evidence at
`/tmp/motorsportverse-event-identity/official-grid-baseline-sources.txt`, hash
`97907a069fd45a966432b669bd950fcfccc93feda2e7d4a38286d43371bfbada`.
The earlier [retrospective evaluation](../ridge-shadow/evaluation.json) and
[champion input-contract probe](champion-input-contract.json) match the
artifact's supporting hashes. Those diagnostics are not a forward accuracy
record or a win probability.

## Staging and scoring boundaries

`src/stage_grid_baseline.py` accepts only the exact sealed digest. It has no
backdating, force, generation or hold-release option. It requires a recent
official-source comparison, unchanged round/season bytes, no target outcome
and a time before race start. It stages complete bytes and atomically creates
two new records without overwrite. Source/deadline checks run at each link;
a rejected attempt removes only its own newly created files.

The baseline uses `forecastKind: official_grid_baseline`, a content-addressed
baselineId and `evaluationStream: baselines/official_grid`. It never enters
RoundData.classification, predicted feature state, probabilities, the season
tracker, the model registry or current model accuracy. Future scoring must
write a separate result keyed by baselineId and the official outcome hash,
leaving the seal unchanged. No outcome or retrospective grade is added here.

The interface labels the baseline explicitly, shows the seal and source check
separately, and keeps full official qualifying and grid tables. It hides the
baseline when event identity or the current official grid disagrees with the
freeze; the model publication notice remains available.

## Validation and browser review

[Validation](validation.json) records 1,175 passing Python tests (15 skipped),
278 passing frontend tests in 19 suites, Ruff, TypeScript, ESLint, the production
static export with the actual Pages base path, 50 published-data integrity
checks and shared-UI sync. ESLint retains its existing AccuracyDashboardPage
navigation warning. [Preservation](worktree-preservation.json) confirms all
eight unrelated original worktrees and both reviewed F1 heads remain clean;
235 pre-existing data/model files are byte-identical. The laptop-only weekend
navigation branch remains unavailable and was not transferred.

[Actual Chromium review](browser-qa.json) covers home, Singapore, Sepang,
accuracy and calendar at 1440, 768, 390 and 320 pixels, plus keyboard navigation
to the final grid. It checks the two timestamps, original download hash, source
links, independent scoring copy, native disclosure, full qualifying/grid tables,
unchanged withdrawal and absence of the baseline on other events. The panel
fits every tested width. Region screenshots use the same width and a taller
capture viewport to keep the unchanged sticky header outside the region.

- [Desktop baseline](singapore-baseline-1440.png)
- [Mobile baseline](singapore-baseline-390.png)
- [Mobile provenance disclosure](singapore-source-390.png)
- [Mobile page with the publication hold and all sessions](singapore-page-390.png)

The existing Next Race navigation button extends the 768px page to 912px;
the reviewed pre-change export produces the same overflow. This navigation
defect is outside the independent baseline change. Flag/Wikimedia images also
fail through the cloud proxy; local headshots and baseline assets load. Cancelled
prefetch requests during scripted page transitions are recorded separately
from HTTP/network failures. Live public Pages access remains blocked by the
cloud proxy, so these screenshots validate the local production export, not a
deployment. This review branch has not been merged or deployed.

[The final 07:33 UTC official-source check](final-source-recheck.json) still
matches all positions. It does not alter the 06:53 seal or 07:09 staging source
receipt. The race outcome was not fetched.

## Separate penalty-contract repair

[The probe](champion-input-contract.json) confirms that supplying Russell's
qualifying grid or final grid produces identical current model input columns.
The existing grid parameter only orders no-time qualifiers. The race
postprocessor also anchors grid rank on QualifyingRank.

The narrow reusable repair is to carry a separately verified
StartingGridPosition column through the existing post-qualifying seam, keeping
qualifying pace/rank unchanged. Use final grid for grid-anchored postprocessing
and simulator initialization, with full-field/event/source/cutoff validation.
Do not add it to learned feature columns or relabel qualifying as the final
grid. Test a timed driver's penalty, no-time qualifier, missing/contradictory
grid and prior-only provenance; evaluate held-out events before any quality
claim or champion replacement. This PR does not make that model change.
