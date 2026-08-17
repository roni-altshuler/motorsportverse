# Known issues

Defects that are **found, understood and not yet fixed**, each with the gate
that is currently waived for it. Nothing is on this list without a named check
that would otherwise fail — an issue with no failing check is not tracked here,
it is just untested.

The rule: `scripts/validate_published_data.py --allow <check>` is the only way to
carry a known failure, the allowance is written in the workflow that grants it
(never in a config file), and the allowance is deleted in the same PR as the fix.

## Currently allowed

*Nothing.* The gate runs with no `--allow` flags: 407 checks over 11 projects.

## Resolved

### `probability_mass` — calibrated markets did not sum to their set size

**Found:** 2026-08-16, by the first run of `motorsport_core.integrity` over the
whole repo. 129 of 131 failures in that first run were this.

**What it was.** Per-competitor isotonic calibration maps each competitor's
probability independently, so the market it belongs to no longer sums to the
size of the set it describes. A win market must total 1, a podium 3, a
top-six 6, a top-ten 10. Measured across the published corpus:

| series | worst published win-market sum | which markets |
| --- | --- | --- |
| F2 | 1.428 | all four |
| NASCAR | 1.303 | all four |
| Formula E | 1.267 | all four |
| F3 | 1.231 | all four |
| IndyCar | 1.190 | all four |
| MotoGP | 1.000 ✓ | podium / top6 / top10 only |
| WRC | 1.001 ✓ | podium / top6 / top10 only |

The sites render `probability` directly as a percentage, so a reader adding up
a win column got 143%.

**Why it happened, and the part worth remembering.** The flagship had **already
found and fixed this** — its 2026-07-07 audit measured win markets summing to
1.17-1.94, and it shipped `renormalize_market_struct` to water-fill each market
back to its target. But that function lived in
`projects/f1-predictions/models/calibration.py`, not in `motorsport-core`. Every
series cloned from the golden template inherited the calibration step and none
of them inherited the fix. This is the failure mode a monorepo with a shared
package is supposed to prevent, and it went unnoticed because **nothing compared
the published corpus against itself.** Per-file schema tests all passed: every
file was well-formed, and the numbers inside them did not add up.

**The second-generation variant is more interesting than the first.** MotoGP,
WRC, WEC and IMSA were written *after* the problem was understood, and they
each normalise `win` explicitly — with a comment stating that the top-k markets
"are independent per-entry probabilities that legitimately sum to k, so they
are left as-is." That sentence is half true. Top-k probabilities *should* sum
to k; per-competitor calibration is precisely what stops them doing so. `win`
got fixed because it visibly looks like a distribution, and the other three
were reasoned about instead of measured.

**And the near-miss is the most instructive part.** Three projects' schema
mirrors *did* assert a probability sum — but on `rawProbability`:

```python
assert abs(sum(v.rawProbability for v in win.values()) - 1.0) < 0.02
```

`rawProbability` is the empirical Monte-Carlo frequency. It is coherent by
construction and was never the broken field. The field the site actually
renders — `probability`, post-calibration — went unchecked. A test one
identifier away from catching this passed cleanly for a month.

**The fix.** `renormalize_market_struct` now lives in
`motorsport_core.calibration`, where a fix reaches every series at once, and
composes with the small-sample regularisation from `b2765d9` rather than
undoing it: the water-fill respects `CALIBRATION_PROB_FLOOR` as a lower bound,
so scaling a market down cannot reintroduce the hard zeros that floor exists to
prevent. Each series' `export._calibrate_markets` calls it, unrounded, before
publishing — rounding first reintroduces the drift it removes. Every project's
`test_website_data_schema.py` now carries
`test_published_probabilities_sum_to_their_market`, which delegates to the same
`motorsport_core.integrity` check so the rule has one definition.

**Verified:** all nine affected series regenerated; `validate_published_data.py`
reports 0 failures with no `--allow` flags.

---

### WRC's raw top-k markets never summed either

**Found:** 2026-08-16, by the same run — `probability_mass` flagged WRC's
`rawProbability` as well as its calibrated field, which no other series did.

**What it was.** WRC ensembles its skill model with a championship-form prior.
The prior's shape came from hand-assigned constants — `topk(3, 0.7, 0.15, 0.03)`
and friends — which over a 34-crew entry total 3.39 for podium, 8.30 for top-six
and 13.80 for top-ten. Only `win` was normalised. Blended 50/50 with a coherent
model, the published raw values came out at exactly 3.195, 7.150 and 11.900.

This one was **not** a calibration artifact, which is why it matters that the
integrity check tests the raw field separately. Renormalising the calibrated
output alone would have papered over a modelling bug with a presentation fix,
and the raw numbers would have stayed wrong in a field labelled "raw".

**The fix.** The prior is water-filled to its own market size at construction,
so the ensemble blends two coherent inputs and stays coherent by convexity.
`renormalize_market_struct` deliberately does **not** touch `rawProbability`.

---

### `--viz-cat-3` was not colour-blind safe, and the comment claiming it was cited a tool that did not exist

**Found:** 2026-08-16, while porting the chart tokens.

**What it was.** The token block asserted specific measurements — "CVD ΔE 24.2",
"light-end 2.13:1" — attributed to `scripts/validate_palette.js`. That script
existed nowhere in the repo or its history. When it was actually written and
run, the real numbers were different, and `--viz-cat-3: #c25ba6` failed
red-green separation against `--viz-baseline`: ΔE 11.9 protan and 14.7 deutan,
against a floor of 15. Two of three chart series would have been
indistinguishable to a colour-blind reader.

An exhaustive sRGB sweep inside the lightness band found 4252 admissible
replacements — so the earlier note that "adding a third colour fails" was also
wrong, in the more embarrassing direction. `#b75781` keeps the muted-rose
intent and clears every floor at ΔE 20.4 minimum.

**The fix.** `scripts/validate_palette.js` exists, runs in CI
(`--ordinal --pairs all`), and every number in the token comment is now
reproducible from it. The one pair that genuinely cannot clear the floor —
model↔baseline under tritanopia, ΔE 11.9 — is recorded as requiring direct
labelling rather than quietly passing.

**The lesson generalises past colour:** a plausible-looking value that nothing
measured is not a validated value, and a citation to a tool nobody can run is
not evidence.

---

### A time-bomb test, and the CI blind spot that hid it

**Found:** 2026-08-17, by the first CI run to execute the Formula E suite after
the season finished.

**What it was.** `test_composite_qualifying_is_real_only` asserted:

```python
assert src.qualifying(config.SEASON, len(config.CALENDAR)) is None
```

`len(config.CALENDAR)` is the *last round of the season*, used as a stand-in for
"a round that has not been run yet". That is true only while the season is
incomplete. Commit `b0f4976` — a routine Formula E cron data update on
2026-08-16 — pushed `completedRounds` from 16 to 17, London II acquired a
published qualifying order, and the assertion became permanently false.

The test now asks for a round *beyond* the calendar, which is absent no matter
how far the season has progressed, and additionally asserts the property the
docstring actually claims: that a non-`None` answer never came from the
synthetic source.

**The blind spot is the real finding.** Nobody noticed for a day, and the reason
is structural:

1. **Cron commits never run CI.** The update workflows push with
   `GITHUB_TOKEN`, and GitHub deliberately does not trigger workflows on pushes
   made with it. Across the last 40 CI runs, **zero** were for a data commit.
   Every `[series] Update round N` commit reached `main` without CI.
2. **The pre-commit gate in each cron was narrower than the suite.** The crons
   ran `tests/test_website_data_schema.py` only, so a source-layer test could
   not fail the job that broke it.
3. **WEC and IMSA had no pre-commit gate at all** — they installed `pytest` and
   never invoked it.

So the only thing standing between a data commit and GitHub Pages was whichever
subset of tests that cron happened to name. Whatever is not checked *there* is
not checked at all until a human pushes a branch.

**The fix.** Every cron now runs `scripts/validate_published_data.py <project>`
before its commit step, and WEC and IMSA gained the export/model gate they never
had. The corpus check is the right gate for a data commit specifically: the
schema tests prove each file is well-formed, and this proves the numbers inside
them add up.

**The sweep afterwards found three more of the same shape**, all spelling an
absent round as `len(config.CALENDAR)` — one commented, in as many words,
`# finale not yet run`:

| file | fires when |
| --- | --- |
| `f2/tests/test_sources.py` | F2 reaches round 14 (8 to go) |
| `f3/tests/test_sources.py` | F3 reaches round 9 (4 to go) |
| `f3/tests/test_real_data.py` | F3 reaches round 9 (4 to go) |

All now derive the absent round from the snapshot's own `completedRounds`, or
ask for a round beyond the calendar. Formula E broke first only because it is
the first series whose season finished.

Two patterns were checked and cleared rather than assumed guilty:
`config.COMPLETED_ROUNDS + 1` is safe — Formula E is the natural experiment, its
season is complete, it uses that idiom and its suite passes 126/126 — and
`detect_target_round`'s calendar comparison pins to a hard-coded
`datetime(2027, 1, 1)`, which is deterministic on purpose.

**The rule this leaves:** never spell "hasn't happened yet" as a fixed position
in the calendar. Derive it from the data's own progress counter, or step past
the end of the calendar entirely.

**Still open, deliberately:** CI genuinely cannot run on `GITHUB_TOKEN` pushes.
Making it do so means committing with a PAT, which trades a real security
boundary for coverage. The per-cron gates are the cheaper half of that trade and
are what landed; the PAT question is left as a decision rather than assumed.

---

## How to add an entry

1. Add or extend a check in `motorsport_core.integrity` so the defect **fails a
   gate**. An issue nothing detects will be rediscovered, not remembered.
2. Add `--allow <check>` to the CI invocation, with a comment pointing here.
3. Write the entry above: what it is, how it was found, what it affects, why it
   is not fixed yet, and what the fix would be.
4. When the fix lands, move the entry to *Resolved* and delete the allowance in
   the same PR.
