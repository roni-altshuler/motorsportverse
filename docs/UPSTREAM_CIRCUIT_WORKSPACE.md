# Browser-local circuit workspace

F1's `/circuits` page now provides an original local-file consumer of Tom Shaw's
F1 Race Replay output format. Users can select a driver, step saved snapshots,
seek with a native keyboard slider, reset, and change the series workspace.
The optional demonstration uses an original fictional oval and invented drivers.
It is visibly labelled as fictional throughout; it is not Zandvoort or a real race.

This is **interoperability, not vendored upstream algorithms or a licensed
historical replay**. The desktop application supplies processed geometry and
positions in a user-provided file. The browser preserves those samples and uses
native SVG to display them. It does not rebuild telemetry, infer racing lines,
rank drivers, interpolate motion, simulate safety cars or calculate lap/sector
times. No new real telemetry asset or public replay-data endpoint is added.

## Exact upstream audit and reuse decision

Reviewed on 2026-10-08 at
[`efdb8a31900d64e3f269d66601ab9726b7dc5923`](https://github.com/IAmTomShaw/f1-race-replay/tree/efdb8a31900d64e3f269d66601ab9726b7dc5923).
The [README](https://github.com/IAmTomShaw/f1-race-replay/blob/efdb8a31900d64e3f269d66601ab9726b7dc5923/README.md)
declares MIT, but its recursive tree contains no full LICENSE file and GitHub's
repository metadata reports `license: null`.
[Issue #225](https://github.com/IAmTomShaw/f1-race-replay/issues/225) and
[issue #316](https://github.com/IAmTomShaw/f1-race-replay/issues/316) document this
ambiguity. Executable code vendoring is blocked for this PR pending complete
license terms/attribution. No license notice is invented and no upstream package
or desktop process is installed, executed or exposed by the site.

The README separately restricts its data use to educational/noncommercial
purposes and acknowledges ordering errors around starts, pits and finishes.
Safety-car coordinates are simulated. Those statements do not grant third-party
data rights. The official [F1 Guidelines](https://www.formula1.com/en/information/guidelines.4EOKE9RRqevL4niTK9kWyt)
restrict substantial results/timing reuse, commercial use and AI/data-mining use.
This PR does not assert commercial telemetry republication is cleared.

The compatible contract is documented in
[telemetry.md](https://github.com/IAmTomShaw/f1-race-replay/blob/efdb8a31900d64e3f269d66601ab9726b7dc5923/telemetry.md)
and checked against
[`_broadcast_telemetry_state`](https://github.com/IAmTomShaw/f1-race-replay/blob/efdb8a31900d64e3f269d66601ab9726b7dc5923/src/interfaces/race_replay.py).
It is newline-delimited JSON over upstream's local TCP service. A static browser
cannot speak that TCP protocol directly. This page accepts an already-saved
capture; it creates no server, network bridge or unauthenticated stream endpoint.
The reviewed revision identifies the inspected contract, not a verified producer
version for an arbitrary imported file.

## Import contract

Choose a lawfully obtained `.ndjson`, `.jsonl` or single-line `.json` file.
Each nonempty line is one JSON message with `frame_index`, `frame.t` and
`frame.drivers`. Driver entries provide finite X/Y coordinates or a pair of nulls.
An optional `track_geometry` message supplies matching X/Y arrays and
`rotation_deg`. Geometry applies only from that message forward; later updates
cannot supply a missing earlier layout. Paused repeats and rewinds retain their
saved order. Frames are not sorted, interpolated or represented as a full race.

Full driver names are an optional local extension. Otherwise the interface says
“Driver CODE” and “Full name not supplied”; it does not borrow another season's
roster. Missing coordinates and empty driver snapshots remain unavailable.
Sector, lap, gap, ranking, weather and safety-car fields are ignored rather than
turned into inferred values. Only six-digit hex driver colors are accepted.
Native SVG applies the supplied rotation with world-Y flipped for browser display.

Limits: **4 MiB UTF-8, 2,000 snapshots, 4,096 points per geometry, 64 drivers
per snapshot**. Coordinates must be finite and bounded. Invalid JSON, unusable
geometry, unsupported files (including pickle) and oversized files fail with a
recovery action. No code, pickle or arbitrary SVG is evaluated.

Reading is browser-local and transient. Nothing from the capture is uploaded,
persisted or exported. Clear, changing series, unmounting and a newer import
invalidate pending reads. Reload starts empty. There is no automatic playback;
both motion preferences remain static until explicit user input.

## Architecture and preserved scope

The shared `CircuitReplayWorkspace`, strict `replayStream` adapter, original
demo and regressions follow the repository's existing F1-canonical copy/drift
contract across all 11 sites. The production route is mounted only on F1, linked
from its desktop/mobile menu and event pages. Its selector offers all series
with a truthful unavailable state. It creates no Le Mans site, WRC stage model
or automatic reuse of an F1 configuration in another series.

PR #12's image-byte/decode gate and `CircuitExplorer` shell remain intact.
The approved geometry registry is still empty. Legacy hero outlines, quarantined
Austria/Silverstone data, published telemetry/lap assets and licensed artwork
are unchanged. No laptop-only work was transferred or overwritten.

**Real Zandvoort integration remains blocked** by the previously unavailable
licensed original PNG and viewable official configuration reference. Neither is
retried through an alternate access path or replaced by an unverifiable map.
Local-file previews do not register a source as approved or certify event identity.
The demonstration does not complete that source-dependent feature.

## Validation and evidence

The feature's actual flow is menu/event link → static workspace → browser-local
read or lazy original demo → strict adapter → native SVG and snapshot controls.
There is no runtime API/server boundary.

The source contract was inspected; tests use **only original synthetic messages**.
No user-owned real capture or running upstream desktop application has been
verified here. Real-file producer interoperability remains a separate check once
lawfully obtained input is available.

Run the [browser runner](../scripts/qa_circuit_workspace.mjs) after the production
export, supplying the build's configured base path when present:

```sh
node scripts/qa_circuit_workspace.mjs /tmp/circuit-workspace-qa /motorsportverse/projects/f1
```

All 11 sites pass clean locked installs, lint, tests, types and static builds
(2,016 passing frontend tests; eight existing hub skips). F1 also passes Ruff and
its full Python suite (1,087 passed; two skipped).

[Final local checks and browser evidence](qa/circuit-workspace/README.md) record
four desktop/mobile motion cases, visually inspected snapshots, source hashes
and retained network/console observations. No page exceptions or failed local
HTTP resources occurred. External flag-image tunnel failures and cancelled
framework HEAD probes remain in the report; this is not a whole-site or public
deployment approval.
The PR body records the exact final commit and completed CI links. PR #12 stays
draft for independent review; no merge or production job dispatch.
