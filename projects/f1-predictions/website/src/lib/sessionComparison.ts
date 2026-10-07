import { BASE_PATH } from "@/lib/data";
import type { SessionComparisonData } from "@/types";

export const COMPARISON_PATH = `${BASE_PATH}/session-comparison/2025_Monaco_R.json`;
export const COMPARISON_SOURCE_HASH =
  "efb689f9d0f6a9c8133c54b37171084314cb812460b710ab4c206326ee6dd56a";

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function positiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

/** Reject a mislabeled session or incomplete timings before they reach the UI. */
export function validateSessionComparison(value: unknown): SessionComparisonData {
  if (!record(value) || value.schemaVersion !== 1) throw new Error("Invalid archive format");
  const { session, source, drivers } = value;
  if (
    !record(session) ||
    session.id !== "2025_Monaco_R" ||
    session.season !== 2025 ||
    session.event !== "Monaco Grand Prix" ||
    session.kind !== "Race" ||
    session.date !== "2025-05-25" ||
    !record(source) ||
    source.provider !== "FastF1" ||
    source.path !== "features/data/lap_cache/2025_Monaco_R.parquet" ||
    source.sha256 !== COMPARISON_SOURCE_HASH ||
    source.selection !== "fastest-complete-stored-row" ||
    !Array.isArray(source.missingFields) ||
    source.missingFields.join(",") !== "lapNumber,tyre,pitStatus,accuracy,trackStatus" ||
    !Array.isArray(drivers)
  )
    throw new Error("Archive identity could not be verified");

  const codes = new Set<string>();
  for (const driver of drivers) {
    if (
      !record(driver) ||
      typeof driver.code !== "string" ||
      !/^[A-Z]{3}$/.test(driver.code) ||
      codes.has(driver.code) ||
      typeof driver.fullName !== "string" ||
      !driver.fullName.trim() ||
      !(driver.portraitPath === null || driver.portraitPath === `/headshots/${driver.code}.webp`) ||
      !positiveInteger(driver.lapMs) ||
      !positiveInteger(driver.storedRows) ||
      !positiveInteger(driver.completeRows) ||
      driver.completeRows > driver.storedRows ||
      !Array.isArray(driver.sectorMs) ||
      driver.sectorMs.length !== 3 ||
      !driver.sectorMs.every(positiveInteger) ||
      Math.abs(driver.lapMs - driver.sectorMs.reduce((sum, ms) => sum + ms, 0)) > 2
    )
      throw new Error("Archive timings could not be verified");
    codes.add(driver.code);
  }
  return value as unknown as SessionComparisonData;
}

export async function fetchSessionComparison(signal?: AbortSignal): Promise<SessionComparisonData> {
  const response = await fetch(COMPARISON_PATH, { signal });
  if (!response.ok) throw new Error("Archive request failed");
  return validateSessionComparison(await response.json());
}

/** Signed B − A: positive means A's stored timing is quicker. */
export function timingDelta(a: number, b: number): number {
  return b - a;
}

export function formatTimingDelta(deltaMs: number): string {
  return `${deltaMs > 0 ? "+" : deltaMs < 0 ? "−" : ""}${(Math.abs(deltaMs) / 1000).toFixed(3)}s`;
}
