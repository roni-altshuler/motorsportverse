# Circuit geometry evidence and eligibility

The requested shared **Explore circuit** feature is **unfinished**. Of 43 stored
paths across 168 published calendar rounds, 37 outlines remain eligible for
legacy display and zero are reviewed for a new explorer. Legacy presentation
and explorer approval are separate decisions; an empty review registry does not
prove every existing outline is incorrect or forbidden.

## Published coverage

Counts describe committed calendar rounds, not unique venues or independently
verified official calendar completeness. No raw geometry or classifications changed.

| Series | Rounds | Stored paths | Legacy display | Explorer reviewed |
| --- | ---: | ---: | ---: | ---: |
| F1 | 22 | 22 | 20 | 0 |
| F2 | 14 | 12 | 10 | 0 |
| F3 | 9 | 9 | 7 | 0 |
| Formula E | 17 | 0 | 0 | 0 |
| IndyCar | 18 | 0 | 0 | 0 |
| NASCAR | 36 | 0 | 0 | 0 |
| MotoGP | 22 | 0 | 0 | 0 |
| WRC | 13 | 0 | 0 | 0 |
| WEC | 6 | 0 | 0 | 0 |
| IMSA | 11 | 0 | 0 | 0 |
| Le Mans | — | 0 | 0 | 0 |

F1/F2/F3's existing nonconflicting maps and the decorative F1 sweep remain,
without a verification claim. Six Austria/Silverstone entries have identical
outlines under different venue keys and are quarantined. Neither is relabelled
as correct or generic. F1's invented generic fallback is removed. Other sites'
loaders and presentation stay unchanged, with no new empty explorer panels.
Le Mans has no site/calendar; no site was created. WRC stage routes are not
closed circuits, and oval, street, road and multiclass configurations stay distinct.

Hungaroring exports have 16 markers with repeated numbers 1 and 12. The generator
reads FastF1 `Number` and drops `Letter`; repeated numbers may be lost suffixes.
Only those ambiguous markers are suppressed: the same outline and 12 unambiguous
markers remain. No suffix is invented. That unresolved set cannot power a new explorer.
Every stored DRS array is empty and there are no spatial sectors. Numeric counts
cannot locate zones; F1's old nonempty-DRS renderer paints the entire outline.

## Evidence and limits

[Official Silverstone facts](https://www.formula1.com/en/racing/2026/great-britain)
and the [Red Bull Ring F1 reference](https://www.redbullring.com/en/events-tickets/formula-1/formula-1-circuit/)
establish different venues; the [MotoGP layout explanation](https://www.redbullring.com/en/news/premiere-for-new-motogp-chicane-at-red-bull-ring/)
shows that one venue can have different configurations. These references do not
establish our coordinates' source or authorize copying their artwork. None was
copied. Official F1 map images were inaccessible to the reader/proxy, not inspected.

[FastF1 CircuitInfo](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/mvapi/data.py)
uses approximate MultiViewer markers. Our generator tries earlier seasons/fuzzy
event names without exporting the resolved source year/session. No telemetry
cache exists here. Provider labels and timestamps do not fill this gap. The
flagship LICENSE records a fair-use rationale, not third-party permission;
missing review records alone do not revoke existing display or prove infringement.

## Two contracts

The canonical F1 `src/lib/circuitGeometry.ts` travels through the existing shared
copy/drift contract to all other ten sites.

- `assessCircuitOutline` preserves existing nonconflicting outlines, rejects known
  cross-venue/configuration conflicts and malformed outlines, and filters only
  ambiguous/invalid markers without changing raw exports. `legacy-unreviewed`
  never means explorer approval. Existing F1/F2/F3 consumers use this contract.
- `assessCircuitGeometry` gates a **new explorer** on separately reviewed target
  series/season/venue/configuration, dated reference, source-appropriate provenance,
  reuse evidence/basis/attribution, and exact coordinate/corner signature. Geographic
  sources need a pinned map revision, not a fictional timed session. Telemetry
  needs its resolved year/event/session. Do not rename unresolved telemetry as
  geographic data to bypass provenance. The trusted registry remains empty.

Expected configuration comes from event context, not a provider's self-declared
label. Wrong identities, changed geometry, ambiguous corner sets and incomplete
evidence stay ineligible for the new explorer. Synthetic positive tests are QA
only. F1 checks available calendar identity, preserves legacy presentation when
calendar context is unavailable, and still quarantines the exact known conflicting
paths; it makes no additional request.

The decorative CSS sweep remains separate from recorded `RaceTheatre`. No replay
payload is fetched. Preserving that existing sweep does not claim to fix offscreen
behavior; offscreen pause remains a requirement for the future interactive feature.

## Bounded pilot prerequisite

**Monaco is a candidate, not an approved map.** Existing F1/F2/F3 paths and 19 unique
corner markers are identical. The [official 2026 F1 page](https://www.formula1.com/en/racing/2026/monaco)
confirms the 3.337 km event. Restoration commit `7a0e146` records local telemetry
generation but does not resolve its source session/year; timestamps are insufficient.

Pin that candidate, obtain a viewable current official/permitted configuration
reference, compare the outline/direction and each corner, recover source evidence
from existing history/logs where available, and record reuse evidence separately.
The [Will Pittenger Monaco diagram](https://commons.wikimedia.org/wiki/File:Monte_Carlo_Formula_1_track_map.svg)
has an explicit CC BY-SA 3.0 statement but originated in 2009: its license does
not cover our telemetry path and its age does not certify 2026 geometry. Inspecting
these public references needs no credentials or paid access. If current evidence
remains unresolved, keep the explorer gated rather than approving a map by inference.

Once one layout passes, ship a useful accessible pilot on its actual event pages:
intent-loaded geometry, responsive corner buttons/list, keyboard selection, static
reduced motion and offscreen pause, without speed/DRS/sector/replay claims. Reuse in
F2/F3 requires their actual configuration check. Other series keep venue facts until
eligible; WRC needs a stage adapter. This guard does not deliver the interactive feature.

## Reproduce

From the flagship website with existing dependencies:

```bash
npx --no-install tsx ../../../scripts/check_circuit_geometry.ts
npx --no-install tsx ../../../scripts/check_circuit_geometry.ts --require-verified
```

The report separates outline, marker and explorer states. Exit 0 is inventory
completion; `--require-verified` exits 1 for current explorer coverage. CI labels
this audit report only. Green regression tests do not certify layout coverage.
