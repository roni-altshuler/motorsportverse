import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** A rebuild completion marker; it does not establish pre-event publication. */
export interface PublicationExport {
  schemaVersion: 1;
  snapshotSha256: string;
  artifacts: Record<string, string>;
}

export interface PublicationHold {
  schemaVersion: 1;
  sport: "MotoGP";
  status: "held";
  reasonCode: "snapshot-event-identity";
  season: number;
  message: string;
  recovery: string;
  sourceSnapshot: string;
  snapshotSha256: string;
  references: string[];
  issues: {
    code: string;
    message: string;
    round?: number;
    recorded?: { name?: string; venue?: string; date?: string };
    scheduled?: { name?: string; venue?: string; date?: string };
    matchingScheduledRounds?: number[];
  }[];
  routes: { rounds: number[]; riders: string[] };
}

/** A malformed hold never falls through to numerical publication. */
export function getPublicationHold(dataRoot = join(process.cwd(), "public/data")): PublicationHold | null {
  const path = join(dataRoot, "publication_status.json");
  if (!existsSync(path)) return null;
  const value = JSON.parse(readFileSync(path, "utf8")) as PublicationHold;
  if (value.schemaVersion !== 1 || value.sport !== "MotoGP" || value.status !== "held" ||
      value.reasonCode !== "snapshot-event-identity" || !Number.isInteger(value.season) ||
      !value.message || !value.recovery || !/^[a-f0-9]{64}$/.test(value.snapshotSha256) ||
      !Array.isArray(value.issues) || !value.issues.length ||
      !Array.isArray(value.references) || !Array.isArray(value.routes?.rounds) || !Array.isArray(value.routes?.riders)) {
    throw new Error("Malformed MotoGP publication hold");
  }
  if (value.issues.some(issue => !issue || typeof issue.code !== "string" || typeof issue.message !== "string") ||
      value.routes.rounds.some(round => !Number.isInteger(round) || round < 1 || round > 100) ||
      value.routes.riders.some(code => typeof code !== "string" || !/^[A-Z0-9]{2,8}$/.test(code)) ||
      value.references.some(reference => {
        const url = new URL(reference);
        return url.protocol !== "https:" || url.hostname !== "www.motogp.com" || !!url.username || !!url.password;
      })) throw new Error("Malformed MotoGP publication evidence");
  return value;
}
