# Known issues

Defects that are **found, understood and not yet fixed**, each with the gate
that is currently waived for it. Nothing is on this list without a named check
that would otherwise fail — an issue with no failing check is not tracked here,
it is just untested.

The rule: `scripts/validate_published_data.py --allow <check>` is the only way to
carry a known failure, the allowance is written in the workflow that grants it
(never in a config file), and the allowance is deleted in the same PR as the fix.

## Currently allowed

*Nothing.* The gate runs with no `--allow` flags.

## Resolved

### `probability_mass` — calibrated markets did not sum to their set size

**Found:** 2026-08-16, by the first run of `motorsport_core.integrity` over the
whole repo.

**What it was.** Per-competitor isotonic calibration maps each competitor's
probability independently, so the market it belongs to no longer sums to the
size of the set it describes. A win market must total 1, a podium market 3, a
top-six 6, a top-ten 10. Measured across the five cloned series:

| series | worst published win-market sum |
|---|---|
| F2 | 2.00 |
| F3 | 1.60 |
| Formula E | 1.50 |
| IndyCar | 0.50 |
| NASCAR | 0.76 |

The sites render `probability` directly as a percentage, so a reader adding up
the win column on an F3 feature race got 160%.

**Why it happened, and the part worth remembering.** The flagship had **already
found and fixed this** — its own audit on 2026-07-07 measured win markets
summing to 1.17-1.94, and it shipped `renormalize_market_struct` to water-fill
each market back to its target. But that function lived in
`projects/f1-predictions/models/calibration.py`, not in `motorsport-core`. Every
series cloned from the golden template inherited the calibration step and none
of them inherited the fix.

This is the failure mode a monorepo with a shared package is supposed to
prevent, and it went unnoticed for a month because **nothing compared the
published corpus against itself.** Per-file schema tests all passed: every file
was well-formed, and the numbers inside them did not add up.

**And the near-miss is the most instructive part.** Three projects' schema
mirrors *did* assert a probability sum — but on `rawProbability`:

```python
assert abs(sum(v.rawProbability for v in win.values()) - 1.0) < 0.02
```

`rawProbability` is the empirical Monte-Carlo frequency. It is coherent by
construction and was never the broken field. The field the site actually
renders — `probability`, post-calibration — went unchecked. A test one
identifier away from catching this passed cleanly for a month.

Every project's `test_website_data_schema.py` now carries
`test_published_probabilities_sum_to_their_market`, which asserts the
**calibrated** sum across every market of every round.

**The fix.** `renormalize_market_struct` now lives in
`motorsport_core.calibration`, where a fix reaches every series at once. Each
series' `export._calibrate_markets` calls it, unrounded, before publishing —
rounding first reintroduces the drift it removes. `motorsport_core.integrity`'s
`probability_mass` check is the corpus-level regression test, and
`test_market_renormalization.py` is the unit-level one.

**Verified:** all five series regenerated; `validate_published_data.py` reports
0 failures with no `--allow` flags.

---

## How to add an entry

1. Add or extend a check in `motorsport_core.integrity` so the defect **fails a
   gate**. An issue nothing detects will be rediscovered, not remembered.
2. Add `--allow <check>` to the CI invocation, with a comment pointing here.
3. Write the entry above: what it is, how it was found, what it affects, why it
   is not fixed yet, and what the fix would be.
4. When the fix lands, move the entry to *Resolved* and delete the allowance in
   the same PR.
