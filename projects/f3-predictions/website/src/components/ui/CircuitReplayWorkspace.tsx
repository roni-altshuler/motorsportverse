"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  CAPTURE_LIMITS,
  REPLAY_UPSTREAM,
  captureViewport,
  parseReplayCapture,
  type ReplayCapture,
} from "@/lib/replayStream";
import { useReducedMotion } from "@/lib/useReducedMotion";
import CircuitMapUnavailable from "./CircuitMapUnavailable";
import { HUDPanel } from "./HUDPanel";

const SERIES = [
  "Formula 1",
  "Formula 2",
  "Formula 3",
  "Formula E",
  "IndyCar",
  "NASCAR",
  "MotoGP",
  "WRC",
  "WEC",
  "IMSA",
  "Le Mans",
];
const button =
  "min-h-11 border border-[color:var(--hairline-strong)] px-4 py-2 text-sm hover:border-[color:var(--ink)] focus-visible:outline-2! focus-visible:outline-offset-2 focus-visible:outline-[color:var(--ink)] disabled:opacity-40";

/** Original local-file consumer of upstream output, shared by all series sites.
 * Processed geometry and positions come from the capture. No telemetry/network
 * client, reconstructed racing line, safety-car simulation or ranking is added.
 */
export default function CircuitReplayWorkspace() {
  const id = useId();
  const reduced = useReducedMotion();
  const [series, setSeries] = useState(SERIES[0]);
  const [capture, setCapture] = useState<ReplayCapture | null>(null);
  const [snapshot, setSnapshot] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );

  function reset() {
    generation.current++;
    setCapture(null);
    setSnapshot(0);
    setSelected(null);
    setError(null);
    setLoading(false);
    if (fileInput.current) fileInput.current.value = "";
  }
  function commit(value: ReplayCapture) {
    setCapture(value);
    setSnapshot(0);
    setSelected(null);
  }
  async function demo() {
    reset();
    const token = generation.current;
    setLoading(true);
    try {
      const { fictionalCapture } = await import("@/lib/replayStreamDemo");
      if (generation.current === token) commit(fictionalCapture());
    } catch {
      if (generation.current === token) setError("The demonstration could not load. Try again.");
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }
  async function importFile(file: File) {
    reset();
    const token = generation.current;
    setLoading(true);
    try {
      if (!/\.(ndjson|jsonl|json)$/i.test(file.name))
        throw new Error("Choose a JSON, JSONL or NDJSON capture.");
      if (file.size > CAPTURE_LIMITS.bytes)
        throw new Error("This capture exceeds the 4 MiB limit.");
      const text = await file.text();
      if (generation.current !== token) return;
      commit(parseReplayCapture(text, file.name));
    } catch (cause) {
      if (generation.current === token)
        setError(cause instanceof Error ? cause.message : "This capture could not be read.");
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }
  const frame = capture?.frames[snapshot];
  const shape = frame?.geometry;
  const viewport = shape ? captureViewport(shape) : null;
  const driver = frame?.drivers.find((d) => d.code === selected);
  function step(value: number) {
    setSnapshot(value);
  }

  return (
    <section
      aria-label="Circuit workspace"
      className="mx-auto max-w-7xl px-4 pb-20 pt-12 sm:px-8 sm:pt-16"
    >
      <header className="mb-10 max-w-3xl">
        <p className="eyebrow mb-3 text-[color:var(--muted)]">Circuit study · Local workspace</p>
        <h1 className="display-xl">Explore the circuit.</h1>
        <p className="body-lg mt-5 text-[color:var(--body)]">
          Follow a driver through saved snapshots. Open a lawfully obtained capture, or try a
          fictional demonstration.
        </p>
      </header>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-5 border-y border-[color:var(--hairline)] py-5">
        <label className="min-w-48" htmlFor={`${id}-series`}>
          <span className="eyebrow mb-2 block text-[color:var(--muted)]">Series workspace</span>
          <select
            id={`${id}-series`}
            value={series}
            onChange={(e) => {
              reset();
              setSeries(e.target.value);
            }}
            className="min-h-11 w-full border border-[color:var(--hairline-strong)] bg-[color:var(--surface-card)] px-3 text-[color:var(--ink)]"
          >
            {SERIES.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => void demo()} className={button}>
            Try fictional demo
          </button>
          <button type="button" className={button} onClick={() => fileInput.current?.click()}>
            Open local capture
          </button>
          <input
            ref={fileInput}
            id={`${id}-capture`}
            aria-label="Open local capture"
            type="file"
            accept=".json,.jsonl,.ndjson"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void importFile(file);
            }}
          />
          {capture && (
            <button type="button" className={button} onClick={reset}>
              Clear capture
            </button>
          )}
        </div>
      </div>
      <p className="body-sm mb-6 text-[color:var(--muted)]">
        Files stay in this browser tab. Maximum 4 MiB · 2,000 snapshots. Changing series clears the
        capture.
      </p>
      {loading && (
        <div className="mb-6 border border-[color:var(--hairline)] p-6">
          <p role="status">Opening capture…</p>
          <button className={`${button} mt-3`} type="button" onClick={reset}>
            Cancel import
          </button>
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mb-6 border-l-2 border-[color:var(--ink)] bg-[color:var(--surface-card)] p-6"
        >
          <h2 className="title-md">Capture unavailable</h2>
          <p className="body-sm mt-2">{error}</p>
          <button
            className={`${button} mt-4`}
            onClick={() => fileInput.current?.click()}
            type="button"
          >
            Choose another capture
          </button>
        </div>
      )}
      {!capture && !loading && (
        <HUDPanel title="A source comes first" kicker={series} bodyClassName="py-12 sm:py-16">
          <CircuitMapUnavailable />
          <p className="body-sm mx-auto mt-5 max-w-xl text-center text-[color:var(--muted)]">
            No reviewed event map is connected to this workspace. The fictional demo lets you
            explore the controls while a verified circuit source is unavailable.
          </p>
        </HUDPanel>
      )}
      {capture && frame && (
        <>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="eyebrow text-[color:var(--ink)]">
                {capture.source === "fictional"
                  ? "Fictional demo · Not a real circuit or race"
                  : "Local capture · Source and layout unverified"}
              </p>
              <h2 className="title-md mt-2 break-all">{capture.label}</h2>
            </div>
            <p className="body-sm text-[color:var(--muted)]">
              {capture.source === "fictional"
                ? "Original sample coordinates and invented drivers."
                : "Coordinates are supplied by your file; event identity and rights are not certified."}
            </p>
          </div>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1.8fr)_minmax(240px,1fr)]">
            <HUDPanel title="Circuit view" kicker={series} bodyClassName="p-0!">
              <div
                className="relative flex min-h-72 items-center justify-center"
                data-capture-snapshot={snapshot}
                data-motion={reduced ? "reduced-static" : "manual-static"}
              >
                {shape && viewport ? (
                  <svg
                    viewBox={viewport.viewBox}
                    className="aspect-square w-full max-h-[520px]"
                    aria-label={`${capture.source === "fictional" ? "Fictional" : "Unverified local"} circuit view`}
                    role="img"
                  >
                    <g
                      transform={`translate(0 ${viewport.cy * 2}) scale(1 -1) rotate(${shape.rotation} ${viewport.cx} ${viewport.cy})`}
                    >
                      <polyline
                        points={shape.x.map((x, i) => `${x},${shape.y[i]}`).join(" ")}
                        fill="none"
                        stroke="var(--hairline-strong)"
                        strokeWidth={viewport.radius * 0.025}
                        strokeLinejoin="round"
                      />
                      <polyline
                        points={shape.x.map((x, i) => `${x},${shape.y[i]}`).join(" ")}
                        fill="none"
                        stroke="var(--ink)"
                        strokeWidth={viewport.radius * 0.006}
                        strokeLinejoin="round"
                      />
                      {frame.drivers
                        .filter((d) => d.x !== null && d.y !== null)
                        .map((d) => (
                          <circle
                            key={d.code}
                            cx={d.x!}
                            cy={d.y!}
                            r={viewport.radius * (d.code === selected ? 0.036 : 0.022)}
                            fill={d.color}
                            stroke="var(--ink)"
                            strokeWidth={viewport.radius * 0.01}
                            opacity={selected && selected !== d.code ? 0.35 : 1}
                          >
                            <title>{d.name}</title>
                          </circle>
                        ))}
                    </g>
                  </svg>
                ) : (
                  <CircuitMapUnavailable />
                )}
              </div>
              {!shape && (
                <p className="body-sm px-6 pb-6 text-[color:var(--muted)]">
                  This snapshot has no preceding track outline. Driver details remain available.
                </p>
              )}
              <div className="border-t border-[color:var(--hairline)] p-5 sm:p-6">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="eyebrow">
                    Snapshot {snapshot + 1} / {capture.frames.length}
                  </p>
                  <p className="font-mono text-xs text-[color:var(--muted)]">
                    Captured frame {frame.index} · {frame.time.toFixed(2)}s
                  </p>
                </div>
                <label htmlFor={`${id}-snapshot`} className="sr-only">
                  Capture snapshot
                </label>
                <input
                  id={`${id}-snapshot`}
                  type="range"
                  aria-label="Capture snapshot"
                  min={0}
                  max={capture.frames.length - 1}
                  value={snapshot}
                  onChange={(e) => step(Number(e.target.value))}
                  className="mb-4 h-8 w-full accent-[color:var(--ink)]"
                />
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className={button}
                    disabled={snapshot === 0}
                    onClick={() => step(snapshot - 1)}
                  >
                    Previous snapshot
                  </button>
                  <button
                    type="button"
                    className={button}
                    disabled={snapshot === capture.frames.length - 1}
                    onClick={() => step(snapshot + 1)}
                  >
                    Next snapshot
                  </button>
                  <button type="button" className={button} onClick={() => step(0)}>
                    Return to start
                  </button>
                </div>
                <p className="body-sm mt-4 text-[color:var(--muted)]">
                  Snapshots follow saved message order, including pauses and rewinds. No movement is
                  interpolated.
                </p>
              </div>
            </HUDPanel>
            <HUDPanel title="Follow a driver" kicker="Selection">
              {!frame.drivers.length && (
                <p role="status" className="body-sm mb-5 text-[color:var(--muted)]">
                  No driver positions supplied in this snapshot.
                </p>
              )}
              <div className="space-y-2">
                {frame.drivers.map((d) => (
                  <button
                    key={d.code}
                    type="button"
                    className={`${button} flex w-full items-center gap-3 text-left`}
                    aria-pressed={selected === d.code}
                    onClick={() => setSelected(selected === d.code ? null : d.code)}
                    style={{ borderColor: selected === d.code ? "var(--ink)" : undefined }}
                  >
                    <span
                      aria-hidden
                      className="h-3 w-3 shrink-0 rounded-full"
                      style={{ background: d.color }}
                    />
                    <span className="min-w-0">
                      <span className="block">{d.name}</span>
                      {d.name === `Driver ${d.code}` && (
                        <span className="block text-xs text-[color:var(--muted)]">
                          Full name not supplied
                        </span>
                      )}
                    </span>
                  </button>
                ))}
              </div>
              <div className="mt-6 border-t border-[color:var(--hairline)] pt-5" aria-live="polite">
                <p className="eyebrow">
                  {driver ? driver.name : selected ? "Selected driver absent" : "All drivers"}
                </p>
                <p className="body-sm mt-3 text-[color:var(--muted)]">
                  {driver
                    ? driver.x === null
                      ? "Position missing in this snapshot."
                      : "Source position selected for this snapshot."
                    : selected
                      ? "The selected driver is not present in this snapshot."
                      : "Select a driver to highlight their recorded position."}
                </p>
              </div>
              <p className="body-sm mt-6 text-[color:var(--muted)]">
                Ordering, safety-car locations and sector times are not reconstructed in this view.
              </p>
            </HUDPanel>
          </div>
        </>
      )}
      <footer className="body-sm mt-9 max-w-3xl space-y-3 border-t border-[color:var(--hairline)] pt-6 text-[color:var(--muted)]">
        <p>
          Compatible with captures from{" "}
          <a href={REPLAY_UPSTREAM.url} className="underline">
            Tom Shaw’s F1 Race Replay
          </a>
          . Original browser adapter; the desktop application supplies processed geometry and
          positions.
        </p>
        <p>
          Real circuit artwork and historical replay data are unavailable here. The demonstration
          does not establish an event configuration, lap time or racing order.
        </p>
      </footer>
    </section>
  );
}
