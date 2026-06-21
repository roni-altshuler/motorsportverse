import { CalibrationSummary } from "@/types";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";
const BASE_PATH = PREFIX + "/data";

// Build-time read (Node) of the calibration summary. Mirrors the pattern in
// `website/src/lib/value.ts` so the static export can embed the contents at
// module-load time. Reading via `fs` only works on the server; in the browser
// `getCalibrationSummary()` falls back to a runtime fetch.
let BUILD_TIME_CALIBRATION: CalibrationSummary | null = null;

if (typeof window === "undefined") {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("fs") as typeof import("fs");
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const path = require("path") as typeof import("path");

    const filePath = path.join(
      process.cwd(),
      "public",
      "data",
      "probabilities",
      "calibration_summary.json",
    );
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf8");
      BUILD_TIME_CALIBRATION = JSON.parse(raw) as CalibrationSummary;
    }
  } catch {
    BUILD_TIME_CALIBRATION = null;
  }
}

/**
 * Returns the cached, build-time-loaded calibration summary (or null if the
 * file was missing / malformed). This is synchronous so it can be consumed by
 * server components or client components mounting with a build-time payload.
 */
export function getCalibrationSummary(): CalibrationSummary | null {
  return BUILD_TIME_CALIBRATION;
}

/**
 * Runtime fetch of the calibration summary. Useful for client components that
 * want to refresh the data without a full rebuild. Returns null on 404 / parse
 * failure.
 */
export async function fetchCalibrationSummary(): Promise<CalibrationSummary | null> {
  try {
    const res = await fetch(`${BASE_PATH}/probabilities/calibration_summary.json`);
    if (!res.ok) return null;
    return (await res.json()) as CalibrationSummary;
  } catch {
    return null;
  }
}
