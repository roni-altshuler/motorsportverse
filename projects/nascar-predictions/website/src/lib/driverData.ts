/**
 * Pure aggregation helpers for the /driver/[code] profile pages.
 *
 * NASCAR ships ONE combined `nascar.json` (season summary + standings +
 * championship) rather than F1's split season.json / standings.json, so unlike
 * the flagship this module carries no fetch surface of its own — the profile
 * page pulls `NascarData` via `useSeasonNascarData()` and per-round detail via
 * `fetchRoundDetail()` (both in `@/lib/nascarclient`) and feeds the already-
 * fetched objects into the pure functions below. Everything here is a pure
 * function of its inputs, so it stays trivially unit-testable and safe to import
 * from server or `"use client"` code.
 *
 * Every helper is null-tolerant and renders only what the data supports (reserve
 * drivers, pre-race weeks, cars that never started a given round).
 */
import type {
  DriverStanding,
  RoundDetail,
  TitleOdds,
} from "@/types/nascar";

// ---------------------------------------------------------------------------
// Finish-status vocabulary. NASCAR classifies EVERY car that took the green, so
// a finishing position always exists; the running status is what separates a
// clean finish from a DNF. Anything other than "Running" (crash / mechanical)
// is a retirement. "Unknown" is treated as a non-DNF start — it is ambiguous
// provenance, never an affirmative retirement, so we never over-count DNFs.
// ---------------------------------------------------------------------------
const FINISHED_STATUS = "Running";
const AMBIGUOUS_STATUS = "Unknown";

export function isDnfStatus(status: string | null | undefined): boolean {
  if (status == null) return false;
  return status !== FINISHED_STATUS && status !== AMBIGUOUS_STATUS;
}

/** One driver's result for one round — predicted vs actual, plus finish status. */
export interface DriverRoundResult {
  round: number;
  venueKey: string;
  /** Marketing race title, else the venue name. */
  name: string;
  date: string | null;
  /** Predicted finishing position (model output). Present for every round. */
  predictedPosition: number | null;
  /** Actual finishing position — only once the round has been classified. */
  actualPosition: number | null;
  /** Official running status string ("Running" / "Accident" / "Engine" …). */
  status: string | null;
  /** Championship points scored in the race (derived from pointsHistory delta). */
  points: number | null;
  /** True when the driver started but did not finish running (crash/mechanical). */
  dnf: boolean;
  /** True once an official finishing position exists for this round. */
  completed: boolean;
}

/**
 * Distil one round file into this driver's predicted-vs-actual result. Both the
 * predicted and actual position live on the round's `classification` entry
 * (`position` = model call, `actualPosition` = classified result); the running
 * status comes from `actualStatus`. `pointsScored` is passed in from the
 * standings `pointsHistory` delta because the round file carries no per-driver
 * race points.
 */
export function driverRoundResult(
  round: RoundDetail,
  code: string,
  pointsScored: number | null = null,
): DriverRoundResult {
  const entry = round.race?.classification?.find((c) => c.code === code) ?? null;
  const predictedPosition = entry?.position ?? null;

  let actualPosition = entry?.actualPosition ?? null;
  // Fallback to the compact actualResults list when the classification entry
  // did not carry the actual (older baked rounds).
  if (actualPosition == null && round.race?.actualResults) {
    actualPosition =
      round.race.actualResults.find((r) => r.code === code)?.position ?? null;
  }

  const status = round.race?.actualStatus?.[code] ?? null;
  const completed = actualPosition != null;

  return {
    round: round.round,
    venueKey: round.venueKey,
    name: round.raceName || round.venueName,
    date: round.raceDate ?? null,
    predictedPosition,
    actualPosition,
    status,
    points: pointsScored,
    dnf: completed && isDnfStatus(status),
    completed,
  };
}

/** Reliability summary derived from a driver's classified rounds. */
export interface DriverReliability {
  /** Rounds the driver actually has a classified finish for. */
  starts: number;
  /** Rounds finished running to the flag. */
  finishes: number;
  /** Rounds started but retired (crash / mechanical). */
  dnfs: number;
  /** DNFs / starts as a fraction in [0, 1], or null when no starts recorded. */
  dnfRate: number | null;
}

export function computeReliability(results: DriverRoundResult[]): DriverReliability {
  const started = results.filter((r) => r.completed);
  const dnfs = started.filter((r) => r.dnf).length;
  const starts = started.length;
  return {
    starts,
    finishes: starts - dnfs,
    dnfs,
    dnfRate: starts > 0 ? dnfs / starts : null,
  };
}

/** Best (lowest) classified finishing position across completed rounds. */
export function bestFinish(results: DriverRoundResult[]): number | null {
  const positions = results
    .filter((r) => r.completed)
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/**
 * Cumulative points-progression series for the chart, derived from the driver
 * standings `pointsHistory` (cumulative per completed round). Also exposes the
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

/**
 * Per-round points scored, keyed by round number (1-based over completed
 * rounds). Used to fill the "Pts" column of the predicted-vs-actual table.
 */
export function pointsByRound(
  history: number[] | undefined | null,
): Record<number, number> {
  const out: Record<number, number> = {};
  for (const p of pointsProgression(history)) out[p.round] = p.delta;
  return out;
}

/** Sum of the last `n` per-round point deltas — a compact recent-form signal. */
export function recentForm(history: number[] | undefined | null, n = 3): number {
  const prog = pointsProgression(history);
  return prog.slice(-n).reduce((sum, p) => sum + p.delta, 0);
}

/** Find a driver's standings record by code. */
export function findStanding(
  standings: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return standings?.find((d) => d.code === code) ?? null;
}

/** Find a driver's championship (title-odds) record by code. */
export function findChampionship(
  championship: TitleOdds[] | undefined | null,
  code: string,
): TitleOdds | null {
  return championship?.find((c) => c.code === code) ?? null;
}

/**
 * Every driver code known to the season — the standings roster (also anyone who
 * only appears in the championship projection). Used by `generateStaticParams`
 * (server) and to validate a requested code (client).
 */
export function allDriverCodes(
  standings: DriverStanding[] | undefined | null,
  championship: TitleOdds[] | undefined | null,
): string[] {
  const codes = new Set<string>();
  standings?.forEach((d) => d.code && codes.add(d.code));
  championship?.forEach((c) => c.code && codes.add(c.code));
  return Array.from(codes);
}
