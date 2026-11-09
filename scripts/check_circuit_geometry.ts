// Read-only inventory. Run with the flagship's installed tsx; no provider calls.
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { getPublicationHold } from "../projects/motogp-predictions/website/src/lib/publication";
import {
  assessCircuitGeometry,
  assessCircuitOutline,
  type CircuitCandidate,
  type CircuitShape,
} from "../projects/f1-predictions/website/src/lib/circuitGeometry";
import { CIRCUIT_GEOMETRY_REVIEWS } from "../projects/f1-predictions/website/src/lib/circuitGeometryReviews";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sources = [
  ["f1", "season"],
  ["f2", "f2"],
  ["f3", "f3"],
  ["formula-e", "fe"],
  ["indycar", "indycar"],
  ["nascar", "nascar"],
  ["motogp", "motogp"],
  ["wrc", "wrc"],
  ["wec", "wec"],
  ["imsa", "imsa"],
  ["lemans", null],
] as const;
interface CalendarEntry {
  round: number;
  key?: string;
  gpKey?: string;
  name: string;
  circuit?: string;
  layoutId?: string;
}
function read<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

export function auditCircuitGeometry(repoRoot = root) {
  return sources.map(([series, filename]) => {
    if (!filename)
      return {
        series,
        rounds: null,
        stored: 0,
        verified: 0,
        status: "no-site",
        entries: [],
      };
    const dataDir = resolve(
      repoRoot,
      `projects/${series}-predictions/website/public/data`,
    );
    if (series === "motogp") {
      const hold = getPublicationHold(dataDir);
      if (hold) {
        const snapshot = `projects/motogp-predictions/data/official_${hold.season}.json`;
        if (hold.sourceSnapshot !== snapshot ||
            createHash("sha256").update(readFileSync(resolve(repoRoot, snapshot))).digest("hex") !== hold.snapshotSha256)
          throw new Error("MotoGP publication hold does not match its preserved source snapshot");
        if (["motogp.json", "rounds", "probabilities", "forward_eval", "evidence.json", "model_health.json", "calibration_summary.json"]
          .some(name => existsSync(resolve(dataDir, name))))
          throw new Error("MotoGP publication hold coexists with numerical artifacts");
        return { series, rounds: null, stored: 0, verified: 0, status: "publication-held", message: hold.message, entries: [] };
      }
    }
    const data = read<{ season: number; calendar: CalendarEntry[] }>(
      resolve(dataDir, `${filename}.json`),
    );
    const libraryPath = resolve(dataDir, "circuits.json");
    const library = existsSync(libraryPath)
      ? read<Record<string, CircuitShape>>(libraryPath)
      : {};
    const candidates = data.calendar.map((entry) => {
      const roundPath = resolve(
        dataDir,
        `rounds/round_${String(entry.round).padStart(2, "0")}.json`,
      );
      const roundGeometry = existsSync(roundPath)
        ? read<{ circuitInfo?: { geometry?: CircuitShape } }>(roundPath)
            .circuitInfo?.geometry
        : null;
      return {
        series,
        season: data.season,
        venueKey: entry.gpKey ?? entry.key ?? "",
        layoutId: entry.layoutId,
        geometry:
          series === "f1"
            ? roundGeometry
            : (library[entry.key ?? ""] ?? roundGeometry),
      } satisfies CircuitCandidate;
    });
    const entries = candidates.map((candidate, index) => ({
      round: data.calendar[index].round,
      venueKey: candidate.venueKey,
      venue: data.calendar[index].circuit ?? data.calendar[index].name,
      outlineStatus: assessCircuitOutline(candidate, candidate.geometry, candidates).status,
      cornerMarkersSuppressed: assessCircuitOutline(candidate, candidate.geometry, candidates).cornersSuppressed ?? false,
      status: assessCircuitGeometry(
        candidate,
        candidate.geometry,
        candidates,
        CIRCUIT_GEOMETRY_REVIEWS,
      ).status,
    }));
    return {
      series,
      rounds: data.calendar.length,
      stored: candidates.filter((entry) => entry.geometry?.path).length,
      legacyDisplay: entries.filter((entry) => entry.outlineStatus === "legacy-unreviewed").length,
      verified: entries.filter((entry) => entry.status === "verified").length,
      status: "audited",
      entries,
    };
  });
}

export function hasCompleteVerifiedGeometry(report: readonly { status: string; verified: number; rounds: number | null }[]): boolean {
  return report.every(entry => entry.status === "audited" && entry.verified === entry.rounds);
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const report = auditCircuitGeometry();
  console.log(JSON.stringify(report, null, 2));
  // Inventory completion is not approval. Callers can explicitly require coverage.
  if (
    process.argv.includes("--require-verified") &&
    !hasCompleteVerifiedGeometry(report)
  )
    process.exitCode = 1;
}
