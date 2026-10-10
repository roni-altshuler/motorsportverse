# Deterministic freshness tests — 2026-10-10

The four failures on base `ebfa752ad1f4c29f437358f099c354e0b74c9f6e`
come from scenario tests importing recurring published exports. They are not a
wall-clock or date-boundary defect. The tests were added in `56791709`; the
October 10 export update `48042c34` replaced their implicit fixture assumptions.
Production freshness logic and published data are unchanged by this correction.

| Original failing scenario | Old expectation | Actual unchanged base input/behavior | Cause |
| --- | --- | --- | --- |
| Independent dates, estimated inputs | Ranking: 27 Jun 2026, 17:06:41 UTC; probability: 27 Sept 2026, 01:06:55 UTC; estimated qualifying and static weather | Ranking: 10 Oct 2026, 10:22:59 UTC; probability: 10 Oct 2026, 10:25:41 UTC; verified-grid metadata and API weather | The imported exports changed. The ranking-older warning and unknown-cutoff behavior still agree with these inputs. |
| Older probability warning | Probability older | The test passes its fixed September probability date as the *ranking* argument and the imported October ranking date as the *probability* argument. The first argument is older, so the actual note says ranking older. | Replacing the live June date with October reverses the test's intended ordering. |
| Conflicting source metadata | Qualifying conflict and weather conflict | Qualifying still conflicts. Both overridden declared weather and inherited recorded weather now say `api`, so actual weather is “API weather recorded.” | The old recorded `static` weather source was an implicit fixture dependency. |
| Absent factors and graded hiding | “Factor data unavailable” | All three podium entries, and all 22 classification entries, now have factors. The panel displays the recorded breakdown. | The updated export contains the data whose absence the test intended to exercise. |

An isolated detached checkout of the exact base and the uncorrected PR head use
the same locked dependencies, Node 20.20.2 / npm 10.9.9, timezone UTC, and
`2026-10-10T00:00:00Z` system clock: both reproduce **four failed / 19 passed**.
The exact base also reproduces the same four failures with clocks fixed at
June 27 and September 27. Corrected tests pass **25/25** at all three clocks.
[Structured observations and hashes](freshness-diagnosis.json) and
[original logs](freshness-clock-logs.tar.gz) preserve the evidence.

The correction gives estimated, verified, conflicting, reverse-order and absent
factor scenarios small explicit typed fixtures. All original freshness assertions
remain, including invalid/missing timestamps, identity conflicts, independent
exports, unknown input cutoff, warning direction and graded hiding. Two added
checks retain current-export timestamp wiring and recorded-factor visibility on
graded exports. No timestamp, source, model output, production component or
freshness rule is changed; no test is skipped or expected failure suppressed.

To reproduce the fixed-clock runs, create a temporary setup file:

```js
beforeAll(() => {
  jest.useFakeTimers({ now: new Date(process.env.FRESHNESS_TEST_CLOCK) });
});
afterAll(() => jest.useRealTimers());
```

Run from the F1 website with the existing setup retained:

```sh
TZ=UTC FRESHNESS_TEST_CLOCK=2026-10-10T00:00:00Z npm test -- --ci --runInBand \
  src/__tests__/predictionFreshness.test.tsx --setupFilesAfterEnv \
  ./jest.setup.js /absolute/path/to/frozen-freshness-clock.cjs
```

Repeat at `2026-06-27T00:00:00Z` and `2026-09-27T00:00:00Z`. To reproduce the
failures, use a separate checkout at the base SHA with its unchanged test/data;
do not replace a served export with a synthetic fixture.
