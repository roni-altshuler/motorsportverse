/**
 * Data loaders + pure aggregation helpers for the /driver/[code] profile pages.
 *
 * This module deliberately does NOT touch the shared `src/lib/data.ts` — it
 * replicates the minimal fetch surface it needs (season, standings, round JSON)
 * so the driver-profile feature is self-contained. Every fetch is null-tolerant
 * and every aggregation renders only what the JSON actually provides.
 *
 * The base-path convention mirrors `data.ts`: the active season lives at
 * `/data`; archived seasons live at `/data/seasons/<year>`. Callers pass the
 * `basePath` resolved by `useSeason()` so the same code works under the GitHub
 * Pages prefix and local `npm run dev`.
 */
import type {
  SeasonData,
  StandingsData,
  RoundData,
  DriverStanding,
  DriverInfo,
  ClassificationEntry,
  WeekendResultRow,
} from "@/types";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";

/** Data root for the active season. Pass an override for archived seasons. */
export const DRIVER_DATA_BASE = PREFIX + "/data";

export async function fetchSeasonJson(
  base: string = DRIVER_DATA_BASE,
): Promise<SeasonData> {
  const res = await fetch(`${base}/season.json`);
  if (!res.ok) throw new Error("Failed to fetch season data");
  return res.json();
}

export async function fetchStandingsJson(
  base: string = DRIVER_DATA_BASE,
): Promise<StandingsData> {
  const res = await fetch(`${base}/standings.json`);
  if (!res.ok) throw new Error("Failed to fetch standings data");
  return res.json();
}

/**
 * One round's JSON. Not every round has been run — future rounds still ship a
 * predicted `classification` but carry no `actualResults`. Returns null instead
 * of throwing so consumers degrade gracefully.
 */
export async function fetchRoundJson(
  round: number,
  base: string = DRIVER_DATA_BASE,
): Promise<RoundData | null> {
  try {
    const pad = round.toString().padStart(2, "0");
    const res = await fetch(`${base}/rounds/round_${pad}.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Pure aggregation helpers (unit-testable; operate on already-fetched data).
// ---------------------------------------------------------------------------

/** Statuses that represent a classified running finish (still counts as a start). */
const FINISHED_STATUSES = new Set(["Finished", "Lapped"]);
/** Statuses that represent a did-not-finish (started, but retired/excluded). */
const DNF_STATUSES = new Set(["Retired", "Disqualified"]);
/** Status that represents a non-start (excluded from the "starts" denominator). */
const DNS_STATUSES = new Set(["Did not start", "Did Not Start", "Withdrawn"]);

/** One driver's result for one round — predicted vs actual, plus finish status. */
export interface DriverRoundResult {
  round: number;
  gpKey: string;
  name: string;
  date: string | null;
  /** Predicted finishing position (model output). Present for every round. */
  predictedPosition: number | null;
  /** Actual finishing position — only once the round has been classified. */
  actualPosition: number | null;
  /** Starting grid slot, when the race result carries it. */
  grid: number | null;
  /** Race-result status string ("Finished" / "Lapped" / "Retired" / …). */
  status: string | null;
  /** Actual championship points scored in the race, when available. */
  points: number | null;
  /** True when the driver started but did not finish (retired/DSQ). */
  dnf: boolean;
  /** True when the driver did not start the race. */
  dns: boolean;
  /** True once an official finishing position exists for this round. */
  completed: boolean;
}

function findRaceRow(round: RoundData, code: string): WeekendResultRow | null {
  const sessions = round.weekendResults?.sessions ?? [];
  const race = sessions.find((s) => s.kind === "race");
  if (!race?.rows) return null;
  return race.rows.find((r) => r.driver === code) ?? null;
}

/**
 * Map the compact `actualStatus` code ("R"/"W"/numeric) used on older round
 * JSONs to the verbose status vocabulary the race-result rows use.
 */
function statusFromCode(code: string | undefined): string | null {
  if (code == null) return null;
  if (code === "R") return "Retired";
  if (code === "W") return "Did not start";
  if (code === "D") return "Disqualified";
  if (/^\d+$/.test(code)) return "Finished";
  return code;
}

/**
 * Distil one round file into this driver's predicted-vs-actual result. Prefers
 * the rich race-result rows (position/grid/status/points); falls back to the
 * compact `actualResults` + `actualStatus` maps when rows are absent.
 */
export function driverRoundResult(
  round: RoundData,
  code: string,
): DriverRoundResult {
  const predicted =
    round.classification?.find((c) => c.driver === code)?.position ?? null;

  const row = findRaceRow(round, code);

  let actualPosition: number | null = null;
  let grid: number | null = null;
  let status: string | null = null;
  let points: number | null = null;

  if (row) {
    actualPosition = row.position ?? null;
    grid = row.grid ?? null;
    status = row.status ?? null;
    points = row.points ?? null;
  } else if (round.actualResults && round.actualResults[code] != null) {
    actualPosition = round.actualResults[code];
    status = statusFromCode(round.actualStatus?.[code]);
  }

  const dnf = status != null && DNF_STATUSES.has(status);
  const dns = status != null && DNS_STATUSES.has(status);
  const completed = actualPosition != null;

  return {
    round: round.round,
    gpKey: round.gpKey,
    name: round.name,
    date: round.date ?? null,
    predictedPosition: predicted,
    actualPosition,
    grid,
    status,
    points,
    dnf,
    dns,
    completed,
  };
}

/** Reliability summary derived from a driver's classified rounds. */
export interface DriverReliability {
  /** Rounds the driver actually started (finishes + DNFs; excludes DNS). */
  starts: number;
  /** Rounds finished (classified, running to the flag or lapped). */
  finishes: number;
  /** Rounds started but not finished (retired / disqualified). */
  dnfs: number;
  /** DNFs / starts as a fraction in [0, 1], or null when no starts recorded. */
  dnfRate: number | null;
}

export function computeReliability(results: DriverRoundResult[]): DriverReliability {
  const started = results.filter((r) => r.completed && !r.dns);
  const dnfs = started.filter((r) => r.dnf).length;
  const starts = started.length;
  return {
    starts,
    finishes: starts - dnfs,
    dnfs,
    dnfRate: starts > 0 ? dnfs / starts : null,
  };
}

/**
 * Mean predicted retirement risk the model assigned this driver across the
 * rounds where it published a `dnfProbability`. This is model output, distinct
 * from the observed DNF rate above — surfaced side-by-side for honesty.
 */
export function meanPredictedDnfRisk(entries: ClassificationEntry[]): number | null {
  const vals = entries
    .map((e) => e.dnfProbability)
    .filter((v): v is number => typeof v === "number");
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Best (lowest) classified finishing position across completed rounds. */
export function bestFinish(results: DriverRoundResult[]): number | null {
  const positions = results
    .filter((r) => r.completed && !r.dnf && !r.dns)
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/**
 * Cumulative points-progression series for the chart. Derived from
 * standings.json `pointsHistory` (cumulative per round). Also exposes the
 * per-round delta so the tooltip can show "points scored this round".
 */
export interface PointsProgressionPoint {
  round: number;
  label: string;
  cumulative: number;
  delta: number;
}

export function pointsProgression(
  history: number[] | undefined | null,
): PointsProgressionPoint[] {
  if (!history || history.length === 0) return [];
  return history.map((cum, i) => ({
    round: i + 1,
    label: `R${i + 1}`,
    cumulative: cum,
    delta: i === 0 ? cum : cum - history[i - 1],
  }));
}

/** Sum of the last `n` per-round point deltas — a compact recent-form signal. */
export function recentForm(history: number[] | undefined | null, n = 3): number {
  const prog = pointsProgression(history);
  return prog.slice(-n).reduce((sum, p) => sum + p.delta, 0);
}

/** Find a driver's standings record by 3-letter code. */
export function findStanding(
  standings: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return standings?.find((d) => d.driver === code) ?? null;
}

/** Find a driver's season-roster info (number, team) by 3-letter code. */
export function findDriverInfo(
  drivers: DriverInfo[] | undefined | null,
  code: string,
): DriverInfo | null {
  return drivers?.find((d) => d.code === code) ?? null;
}

/**
 * Enumerate every driver code known to the season — the roster plus anyone who
 * appears in the standings (covers mid-season debuts / reserves). Used both by
 * `generateStaticParams` (server) and to validate a requested code (client).
 */
export function allDriverCodes(
  season: Pick<SeasonData, "drivers"> | null,
  standings: Pick<StandingsData, "drivers"> | null,
): string[] {
  const codes = new Set<string>();
  season?.drivers?.forEach((d) => d.code && codes.add(d.code));
  standings?.drivers?.forEach((d) => d.driver && codes.add(d.driver));
  return Array.from(codes);
}
