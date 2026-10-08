/** Original browser adapter for Tom Shaw's documented JSON stream contract.
 * No upstream executable code or telemetry is included. No ranking, track
 * derivation, interpolation or safety-car simulation is performed here.
 */
export const REPLAY_UPSTREAM = {
  revision: "efdb8a31900d64e3f269d66601ab9726b7dc5923",
  url: "https://github.com/IAmTomShaw/f1-race-replay",
} as const;
export const CAPTURE_LIMITS = { bytes: 4 * 1024 * 1024, frames: 2000, points: 4096, drivers: 64 };
export interface CaptureGeometry {
  x: number[];
  y: number[];
  rotation: number;
}
export interface CaptureDriver {
  code: string;
  name: string;
  x: number | null;
  y: number | null;
  color: string;
}
export interface CaptureFrame {
  index: number;
  time: number;
  drivers: CaptureDriver[];
  geometry: CaptureGeometry | null;
}
export interface ReplayCapture {
  frames: CaptureFrame[];
  source: "local" | "fictional";
  label: string;
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function coordinate(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && Math.abs(value) <= 1e7;
}
function geometry(value: unknown): CaptureGeometry {
  if (
    !record(value) ||
    !Array.isArray(value.x) ||
    !Array.isArray(value.y) ||
    value.x.length < 3 ||
    value.x.length > CAPTURE_LIMITS.points ||
    value.x.length !== value.y.length ||
    !value.x.every(coordinate) ||
    !value.y.every(coordinate) ||
    (value.rotation_deg !== undefined &&
      (!coordinate(value.rotation_deg) || Math.abs(value.rotation_deg) > 360))
  ) {
    throw new Error("Track coordinates must contain 3–4096 matching, finite X/Y points.");
  }
  const x = value.x as number[],
    y = value.y as number[];
  if (Math.max(...x) === Math.min(...x) || Math.max(...y) === Math.min(...y))
    throw new Error("Track coordinates need a two-dimensional outline.");
  return { x, y, rotation: (value.rotation_deg as number | undefined) ?? 0 };
}

/** Captures preserve received order, pauses, rewinds and missing positions.
 * Geometry only applies from the message that supplies it onward. A later
 * geometry update never rewrites earlier snapshots; frame times aren't guessed.
 */
export function parseReplayCapture(text: string, label: string): ReplayCapture {
  if (new Blob([text]).size > CAPTURE_LIMITS.bytes)
    throw new Error("This capture exceeds the 4 MiB limit.");
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .filter((line) => line.trim());
  if (!lines.length || lines.length > CAPTURE_LIMITS.frames)
    throw new Error("Choose a capture containing 1–2000 JSON snapshots.");
  let currentGeometry: CaptureGeometry | null = null;
  const frames = lines.map((line, lineIndex): CaptureFrame => {
    let message: unknown;
    try {
      message = JSON.parse(line);
    } catch {
      throw new Error(`Snapshot ${lineIndex + 1} is not valid JSON.`);
    }
    if (
      !record(message) ||
      !record(message.frame) ||
      !record(message.frame.drivers) ||
      !Number.isSafeInteger(message.frame_index) ||
      (message.frame_index as number) < 0 ||
      !coordinate(message.frame.t) ||
      message.frame.t < 0
    )
      throw new Error(`Snapshot ${lineIndex + 1} needs frame_index, frame.t and frame.drivers.`);
    if (message.track_geometry !== undefined) currentGeometry = geometry(message.track_geometry);
    const entries = Object.entries(message.frame.drivers);
    if (entries.length > CAPTURE_LIMITS.drivers)
      throw new Error(`Snapshot ${lineIndex + 1} exceeds the 64-driver limit.`);
    const colors = record(message.driver_colors) ? message.driver_colors : {};
    const drivers = entries.map(([code, value]): CaptureDriver => {
      if (
        !/^[A-Z0-9_-]{1,12}$/.test(code) ||
        ["__PROTO__", "CONSTRUCTOR", "PROTOTYPE"].includes(code) ||
        !record(value) ||
        (value.x !== null && !coordinate(value.x)) ||
        (value.y !== null && !coordinate(value.y)) ||
        (value.x === null) !== (value.y === null)
      )
        throw new Error(`Snapshot ${lineIndex + 1} has an invalid driver position.`);
      // Full names are an optional local extension. Upstream commonly supplies
      // only codes; don't attach a guessed season's identity to an imported code.
      const name =
        typeof value.name === "string" && value.name.trim() && value.name.length <= 80
          ? value.name.trim()
          : `Driver ${code}`;
      return {
        code,
        name,
        x: value.x as number | null,
        y: value.y as number | null,
        color:
          typeof colors[code] === "string" && /^#[a-f0-9]{6}$/i.test(colors[code] as string)
            ? (colors[code] as string)
            : "var(--ink)",
      };
    });
    return {
      index: message.frame_index as number,
      time: message.frame.t,
      drivers,
      geometry: currentGeometry,
    };
  });
  return { frames, source: "local", label };
}

export function captureViewport(shape: CaptureGeometry) {
  const cx = (Math.min(...shape.x) + Math.max(...shape.x)) / 2;
  const cy = (Math.min(...shape.y) + Math.max(...shape.y)) / 2;
  const radius =
    (Math.hypot(
      Math.max(...shape.x) - Math.min(...shape.x),
      Math.max(...shape.y) - Math.min(...shape.y),
    ) /
      2) *
    1.16;
  return { cx, cy, radius, viewBox: `${cx - radius} ${cy - radius} ${radius * 2} ${radius * 2}` };
}
