# Circuit geometry evidence and release gate

The proposed shared **Explore circuit** release is deferred. The 6 October 2026
inventory found **43 stored paths, zero reviewed layouts**, across **168 rounds**
in the published calendars. A useful interactive map cannot be released from
these exports without inventing provenance. The approved fallback implements a
shared gate, rejects known identity conflicts, and keeps existing map surfaces
honest. No new explorer controls were added to the sites.

## Published coverage

Counts describe committed calendar rounds, not distinct venues or official
calendar completeness. Double headers can share a venue. No provider was bulk
queried and no exported classifications, geometry or completion flags changed.

| Series | Calendar rounds | Stored paths | Eligible layouts | Existing presentation |
| --- | ---: | ---: | ---: | --- |
| F1 | 22 | 22 | 0 | Existing map becomes an unavailable state; venue facts remain |
| F2 | 14 | 12 | 0 | Existing map becomes unavailable; Miami and Montréal have no stored path |
| F3 | 9 | 9 | 0 | Existing map becomes unavailable |
| Formula E | 17 | 0 | 0 | Existing absent-map behavior; no new explorer |
| IndyCar | 18 | 0 | 0 | Road, street and oval metadata only |
| NASCAR | 36 | 0 | 0 | Existing oval/road metadata; no generic oval drawn |
| MotoGP | 22 | 0 | 0 | Existing venue metadata |
| WRC | 13 | 0 | 0 | Rally surface metadata; special stages are not closed circuits |
| WEC | 6 | 0 | 0 | Existing venue/class metadata; configuration remains unknown |
| IMSA | 11 | 0 | 0 | Existing venue/class metadata; speedway and road configurations cannot be interchanged |
| Le Mans | — | 0 | 0 | Scaffold has no site or published calendar |

Six entries (Austria/Silverstone in F1/F2/F3) have identical outlines under
different venue keys. Both labels are quarantined; this does not decide which
venue the path depicts. Three Hungaroring exports also repeat corner identifiers
(1 and 12). The guard rejects that representation rather than inventing suffixes
or renumbering. The remaining 34 stored entries lack review evidence.

No spatial sectors are exported, and every stored geometry's DRS array is empty.
Numeric DRS counts do not locate zones. The old F1 renderer's nonempty-DRS branch
paints the whole outline, so it must not become a zone visualization.

## What was verified and what remains unknown

The [official F1 Silverstone page](https://www.formula1.com/en/racing/2026/great-britain)
identifies Silverstone and its 5.891 km configuration. The
[Red Bull Ring's official F1 reference](https://www.redbullring.com/en/events-tickets/formula-1/formula-1-circuit/)
lists its own layout and ten corners. The venue's
[MotoGP layout explanation](https://www.redbullring.com/en/news/premiere-for-new-motogp-chicane-at-red-bull-ring/)
also establishes that venue-name matching does not establish identical layouts
across series. These references do **not** establish the source of the stored
coordinates or grant permission to reuse the reference artwork. No artwork was
copied into the product. The official Silverstone map image was inaccessible to
the web reader and returned proxy HTTP 403 from the shell; it was not inspected.

[FastF1's primary CircuitInfo implementation](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/mvapi/data.py)
describes approximate markers supplied by MultiViewer. The repository's generator
tries prior seasons without exporting the resolved source year/session, uses
fuzzy event lookup without its own wrong-event guard, and can synthesize corner
numbers when absent. There is no telemetry cache in this saved environment with
which to recover that evidence. `source: fastf1` and `generatedAt` cannot repair
these gaps. Repository/FastF1 code licensing is not a license for third-party
timing or map data; see the existing flagship LICENSE.

## Gate contract

`src/lib/circuitGeometry.ts` is canonical in F1 and copied, with tests, to every
existing series site and the hub by `scripts/sync_shared_ui.mjs`. Every current
SVG map loader requires the gate. The review registry is deliberately empty.

A future maintainer-reviewed entry must provide:

1. Target series, season, exact venue key and explicit layout/configuration ID.
2. Resolved source year, event, session, venue/configuration and source URL.
3. A dated official/permitted reference check for the target configuration.
4. Recorded reuse basis, evidence URL and attribution; a library license or a
   public webpage alone is insufficient.
5. The exact coordinate signature binding the review to the outline, viewBox,
   corner numbers, positions and names. This is a deterministic binding, not a
   cryptographic signature or an automated rights determination.

The expected layout ID comes from the event calendar, never from the candidate
SVG or a fuzzy venue alias. Different season/series/layout reviews, incomplete
evidence, changed coordinates, malformed corner identities and conflicting
outlines return no geometry. Repeated rounds at one reviewed layout are allowed.
Known conflicting outlines are rejected even without a downloaded catalog.

F1's loader accepts its already-loaded season/calendar as context, checks the
requested round and venue, and strips geometry if identity cannot be established.
It makes no extra network request. Recorded `RaceTheatre` payloads remain
separate; the explorer does not import them. The decorative hero component was
not repurposed as a replay or explorer; gated-out outlines simply leave its
existing backdrop. Raw JSON and local recovery are preserved.

## Reproduce

From the flagship website after installing its existing dependencies:

```bash
npx --no-install tsx ../../../scripts/check_circuit_geometry.ts
npx --no-install tsx ../../../scripts/check_circuit_geometry.ts --require-verified
```

The first command completes an inventory; its exit 0 does not mean maps are
eligible. `--require-verified` exits 1 for today's missing/unreviewed layouts and
Le Mans's absent site. CI runs the inventory explicitly as **report only**;
regression tests enforce the guard and shared-copy consistency.

## Prerequisite for the interactive release

Recover or explicitly document permitted source-session/layout evidence for at
least one useful existing path, correct and review the conflicting entries, and
record the reuse basis. Until then, do not add map controls to every site.
The subsequent bounded release can use the shared shell, per-series adapters,
keyboard/mobile corner selection, reduced motion and offscreen pause. It must
keep road/street/oval/rally distinctions, avoid sectors/DRS/live telemetry claims,
and load geometry on intent. Existing eager-fetch/paused redraw behavior in
`RaceTheatre` needs separate work, not inclusion in the hero.
