import { ValueRoundData, ProbabilityRoundData } from "@/types";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";
const BASE_PATH = PREFIX + "/data";

// At build-time (Node), eagerly scan the filesystem for available value round
// files so the static export knows which rounds exist. At runtime in the
// browser, this is a no-op (file scans aren't possible) and we fall back to
// HEAD-request probing.
let BUILD_TIME_VALUE_ROUNDS: number[] | null = null;
let BUILD_TIME_PROB_ROUNDS: number[] | null = null;

if (typeof window === "undefined") {
  try {
    // Lazy import; only available in Node.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const fs = require("fs") as typeof import("fs");
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const path = require("path") as typeof import("path");

    const scanRounds = (subdir: string): number[] => {
      const dir = path.join(process.cwd(), "public", "data", subdir);
      if (!fs.existsSync(dir)) return [];
      const files = fs.readdirSync(dir);
      const rounds: number[] = [];
      for (const f of files) {
        const match = /^round_(\d{2})\.json$/.exec(f);
        if (match) rounds.push(parseInt(match[1], 10));
      }
      return rounds.sort((a, b) => a - b);
    };

    BUILD_TIME_VALUE_ROUNDS = scanRounds("value");
    BUILD_TIME_PROB_ROUNDS = scanRounds("probabilities");
  } catch {
    BUILD_TIME_VALUE_ROUNDS = [];
    BUILD_TIME_PROB_ROUNDS = [];
  }
}

function pad(round: number): string {
  return round.toString().padStart(2, "0");
}

export async function getValueRoundData(
  round: number,
): Promise<ValueRoundData | null> {
  try {
    const res = await fetch(`${BASE_PATH}/value/round_${pad(round)}.json`);
    if (!res.ok) return null;
    return (await res.json()) as ValueRoundData;
  } catch {
    return null;
  }
}

export async function getProbabilityRoundData(
  round: number,
): Promise<ProbabilityRoundData | null> {
  try {
    const res = await fetch(
      `${BASE_PATH}/probabilities/round_${pad(round)}.json`,
    );
    if (!res.ok) return null;
    return (await res.json()) as ProbabilityRoundData;
  } catch {
    return null;
  }
}

/**
 * Lists rounds that have a value JSON file available.
 *
 * At build time this is computed from the filesystem (module load).
 * In the browser, it probes via HEAD requests against the candidate set
 * passed in (typically completed rounds from season.json), to avoid
 * generating spurious 404s.
 */
export async function listAvailableValueRounds(
  candidateRounds?: number[],
): Promise<number[]> {
  if (typeof window === "undefined") {
    return BUILD_TIME_VALUE_ROUNDS ?? [];
  }
  if (!candidateRounds || candidateRounds.length === 0) return [];
  const checks = candidateRounds.map(async (r) => {
    try {
      const res = await fetch(
        `${BASE_PATH}/value/round_${pad(r)}.json`,
        { method: "HEAD" },
      );
      return res.ok ? r : null;
    } catch {
      return null;
    }
  });
  const results = await Promise.all(checks);
  return results.filter((r): r is number => r !== null).sort((a, b) => a - b);
}

export async function listAvailableProbabilityRounds(
  candidateRounds?: number[],
): Promise<number[]> {
  if (typeof window === "undefined") {
    return BUILD_TIME_PROB_ROUNDS ?? [];
  }
  if (!candidateRounds || candidateRounds.length === 0) return [];
  const checks = candidateRounds.map(async (r) => {
    try {
      const res = await fetch(
        `${BASE_PATH}/probabilities/round_${pad(r)}.json`,
        { method: "HEAD" },
      );
      return res.ok ? r : null;
    } catch {
      return null;
    }
  });
  const results = await Promise.all(checks);
  return results.filter((r): r is number => r !== null).sort((a, b) => a - b);
}

export function formatPct(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSignedPct(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

export function formatCurrency(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

export function formatOdds(odds: number): string {
  if (!Number.isFinite(odds)) return "—";
  return odds.toFixed(2);
}
