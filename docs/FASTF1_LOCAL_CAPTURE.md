# Local FastF1 capture export

Jess Ramos's [FastF1 reel](https://www.instagram.com/reel/Da5qfw9y68b/) demonstrates
local caching and session results, laps, weather and telemetry with Pandas. It
uses FastF1, not another replay repository. MotorsportVerse already has FastF1
session ingestion, weather/features, an archived Monaco lap comparison and a
separate race-replay exporter. Those existing paths are unchanged.

The remaining interoperability gap was the [browser-local circuit workspace](UPSTREAM_CIRCUIT_WORKSPACE.md)'s
NDJSON input. `projects/f1-predictions/src/export_local_capture.py` now converts
a short window from an already-loaded session into that input format. The
optional CLI reads an existing **trusted offline cache**. It has no online mode,
live client, authentication flow, public endpoint, training step or publication
step. No real timing, position, telemetry or circuit asset was fetched or added
to validate this change.

## Use your own lawfully obtained local session

FastF1 is optional for the CLI; importing the converter and `--help` use only the
standard library. The F1 project's existing `fastf1~=3.8.1` requirement admits
the locally installed 3.8.3; no dependency or lock was upgraded. The converter
expects FastF1's DataFrame interface on an already-loaded session. Its samples
must contain `SessionTime` and `Source`.

Keep both your cache and output outside Git working trees and release/static
asset directories. Use only a cache you trust: FastF1's parsed cache uses pickle;
this is not a safe reader for a cache obtained from an untrusted person.

```sh
python projects/f1-predictions/src/export_local_capture.py \
  --cache "$HOME/.cache/my-trusted-fastf1" \
  --output "$HOME/local-f1-window.ndjson" \
  --season 2025 --round 22 --session Race --driver 1 \
  --start 3600 --end 3620 --acknowledge-data-terms
```

The window above is illustrative; it is not a verified Las Vegas data window.
Choose your session's driver number and available session-clock interval.
The exporter accepts one driver and at most 120 seconds, 2,000 native samples
and 4 MiB. It fails rather than silently dropping samples. Invalid session
timestamps fail because their place within the window is unknown. It requires a
new output path and never overwrites an existing file. Missing cached resources fail
locally: offline mode is enabled before the round-number event lookup. It checks
the resolved year, round and session before converting.

In F1's **Circuit workspace**, choose **Formula 1**, open the resulting file and
select the driver. Step the native samples to see the supplied channels. No
circuit outline is inferred; the map remains unavailable. Switching to any
other series clears the capture, and importing this F1-only format under any
other series produces an explicit unsupported-input error. Other series gain
no FastF1 provider coverage from this adapter.

Python callers can use `capture_from_session(session, driver=..., season=...,
round_number=..., session_name=..., start_s=..., end_s=...)` on an already-loaded
session without invoking the cache loader. The converter performs no I/O.

## Units, time and accuracy

The [official Telemetry API source](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/core.py)
defines X/Y/Z in tenths of a metre, speed in km/h, throttle in percent and brake
as a boolean. The exporter converts X/Y to **metres**. Z, DRS, weather, laps,
sectors, classification, gaps and track-status reconstruction are outside this
bounded adapter. Brake is **applied / not applied**, never braking pressure.
Missing/nonfinite channels remain null; the documented invalid throttle 104
does not become 104% or a guessed value.

`SessionTime` is retained in seconds from the session data-stream origin. It is
not lap-relative `Time`, elapsed race time, wall time or a freshly zeroed window.
Car and position samples are separate records on their independent timestamps.
Records sort chronologically; equal timestamps retain source order (car before
position), including duplicates. No nearest-neighbour alignment, carry-forward,
resampling, integration, racing-line derivation or interpolation is added.
The upstream `Source` flag is retained, including interpolated input samples.

The [official accuracy guide](https://github.com/theOehrly/Fast-F1/blob/main/docs/data_reference/howto_accurate_calculations.rst)
describes sparse, jittery data at roughly 4–5 Hz and warns about using merged or
interpolated data for calculations. The API's `Source` identifies a sample's
origin; it does not make every channel in a merged row a measured value. This
adapter reads separate `session.car_data` and `session.pos_data`, never
`lap.get_telemetry()`. Coordinate units are not a spatial-accuracy guarantee.
The workspace labels samples, session time, units and unverified accuracy/rights.

The same API documents weather updates about once a minute. Lap weather access
chooses a sample for a lap; it does not supply instant weather for each telemetry
record. This exporter excludes weather rather than inventing that alignment.

## Software license and data rights are separate

FastF1's [actual LICENSE](https://github.com/theOehrly/Fast-F1/blob/main/LICENSE)
licenses its software under MIT. This adapter is original project code; it
vendors no upstream implementation. MIT does not license F1's telemetry,
timing, maps or other content. The official [Legal Notices](https://www.formula1.com/en/information/legal-notices.7egvZU48hzrypubGBNcQKt)
reserve rights in timing/results and other content and restrict copying and
commercial exploitation. The [F1 Guidelines](https://www.formula1.com/en/information/guidelines.4EOKE9RRqevL4niTK9kWyt)
also restrict substantial timing-data reuse and commercial use. An accessible
API or local cache is not a data-rights grant. The acknowledgement flag does not
certify permission. Users remain responsible for lawful local use; generated
captures must not be committed, hosted, added to release assets or published.

## Engineering verification and remaining limits

[Screenshots, source hashes and complete local checks](qa/local-fastf1/README.md)
record the final engineering verification.

Original synthetic Session/DataFrame fixtures cover native timestamp ordering,
duplicates, identity mismatch, missing/NaN values, units, boolean brake,
determinism, size limits, cache-only call order and output protection. Shared
browser tests cover the importer and explicit unsupported-input states for all
ten non-F1 selector choices. Cloud Chromium QA imports the Python converter's
synthetic output into the actual production export on desktop/mobile under both
motion preferences. It does not substitute a hand-written successful payload
for the Python-to-browser boundary.

No lawfully supplied real cache was available for this task. Synthetic tests
validate engineering and the documented API contract, not real session
availability, real telemetry accuracy, event identity or data rights. Existing
geometry/artwork source gates and the fictional demonstration remain unchanged.
