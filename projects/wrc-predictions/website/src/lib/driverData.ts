/**
 * driverData.ts — pure aggregation helpers for the /driver/[code] profile pages.
 *
 * Wired to WRC's real data contract (`@/types/wrc`): one season file (`wrc.json`)
 * whose `driverStandings[*]` carry the crew identity + cumulative `pointsHistory`,
 * and per-round `rounds/round_NN.json` files that each hold a SINGLE scored
 * classification — a rally has no sprint and no qualifying grid, so every crew
 * result is exactly one per round.
 *
 * This module is intentionally fs-free and framework-free, so it is safe to
 * import from the server page (`generateStaticParams`) and the client profile
 * component alike. Every helper is null-tolerant and renders only what the JSON
 * genuinely provides — no fabricated statuses, times, or points.
 */
import type {
  DriverStanding,
  WrcData,
  RallyBlock,
  RoundDetail,
} from "@/types/wrc";

// The WRC points table (top 10), used only for the per-rally "points" column on
// a crew's profile. Super Sunday / Power Stage bonuses are not modelled here —
// the authoritative season total always comes from the standings row.
const WRC_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1];

function pointsFor(position: number, table: number[]): number {
  return position >= 1 && position <= table.length ? table[position - 1] : 0;
}

/** One crew's result for one rally (round). */
export interface DriverRaceResult {
  round: number;
  venueName: string;
  country: string | null;
  surface: string;
  /** True once this rally has an official classification. */
  completed: boolean;
  /** True when the crew was entered (appears in the classification). */
  entered: boolean;
  /** Model's pre-rally predicted finishing position, when the crew is entered. */
  predictedPosition: number | null;
  /** Official finishing position, once classified. */
  actualPosition: number | null;
  /** Base finishing points (from the WRC top-10 table), else null. */
  points: number | null;
  /** Entered a completed rally but has no classified finish (retired / NC). */
  dnf: boolean;
}

function rallyResult(
  block: RallyBlock,
  round: RoundDetail,
  code: string,
): DriverRaceResult {
  const cls = block.classification.find((c) => c.code === code) ?? null;
  const entered = cls != null;
  const predictedPosition = cls?.position ?? null;

  // The classification row carries the authoritative actualPosition; fall back
  // to the compact actualResults list when a row is somehow absent.
  let actualPosition = cls?.actualPosition ?? null;
  if (actualPosition == null && block.actualResults) {
    actualPosition =
      block.actualResults.find((a) => a.code === code)?.position ?? null;
  }

  const completed = (block.actualResults?.length ?? 0) > 0;
  const points = actualPosition != null ? pointsFor(actualPosition, WRC_POINTS) : null;
  const dnf = entered && completed && actualPosition == null;

  return {
    round: round.round,
    venueName: round.venueName,
    country: round.country,
    surface: round.surface,
    completed,
    entered,
    predictedPosition,
    actualPosition,
    points,
    dnf,
  };
}

/** This crew's single result for one round (or empty when not entered). */
export function driverRoundResults(
  round: RoundDetail,
  code: string,
): DriverRaceResult[] {
  return [rallyResult(round.rally, round, code)].filter((r) => r.entered);
}

/** Flatten a crew's results across every loaded round, in rally order. */
export function driverSeasonResults(
  rounds: RoundDetail[],
  code: string,
): DriverRaceResult[] {
  return rounds
    .slice()
    .sort((a, b) => a.round - b.round)
    .flatMap((r) => driverRoundResults(r, code));
}

/** Reliability summary derived from a crew's classified rallies. */
export interface DriverReliability {
  /** Completed rallies the crew started (finishes + DNFs). */
  starts: number;
  /** Rallies finished / classified. */
  finishes: number;
  /** Rallies started but not classified (retired / NC). */
  dnfs: number;
  /** DNFs / starts as a fraction in [0, 1], or null when no starts recorded. */
  dnfRate: number | null;
}

export function computeReliability(results: DriverRaceResult[]): DriverReliability {
  const started = results.filter((r) => r.completed && r.entered);
  const finishes = started.filter((r) => r.actualPosition != null).length;
  const starts = started.length;
  const dnfs = starts - finishes;
  return {
    starts,
    finishes,
    dnfs,
    dnfRate: starts > 0 ? dnfs / starts : null,
  };
}

/** Best (lowest) classified finishing position across completed rallies. */
export function bestFinish(results: DriverRaceResult[]): number | null {
  const positions = results
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/** Count of points-paying finishes (WRC top 10). */
export function pointsFinishes(results: DriverRaceResult[]): number {
  return results.filter((r) => (r.points ?? 0) > 0).length;
}

/**
 * Cumulative points-progression series for the chart, from the standings row's
 * `pointsHistory` (already cumulative per completed round). The per-round delta
 * powers the tooltip ("points scored this rally").
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

/** Find a crew's standings record by 3-letter code. */
export function findDriverStanding(
  drivers: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return drivers?.find((d) => d.code === code) ?? null;
}

/**
 * Enumerate every crew code known to the season (the full standings roster).
 * Used by `generateStaticParams` (server) and to validate a requested code
 * (client).
 */
export function allDriverCodes(
  data: Pick<WrcData, "driverStandings"> | null,
): string[] {
  const codes = new Set<string>();
  data?.driverStandings?.forEach((d) => d.code && codes.add(d.code));
  return Array.from(codes);
}
