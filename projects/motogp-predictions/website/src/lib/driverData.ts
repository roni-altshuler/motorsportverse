/**
 * driverData.ts — pure aggregation helpers for the /rider/[code] profile pages.
 *
 * Ported in spirit from the RaceIQ F1 flagship's lib/driverData.ts, but wired to
 * MotoGP's real data contract (`@/types/motogp`): one season file (`motogp.json`)
 * whose `driverStandings[*]` carry the identity + cumulative `pointsHistory`, and
 * per round `rounds/round_NN.json` files that each hold TWO scored races — a
 * Saturday `sprint` and a Sunday Grand Prix (the JSON key is `feature`). Both
 * share the qualifying grid (no reverse grid). Every rider result is therefore
 * per-race, not per-round.
 *
 * This module is intentionally fs-free and framework-free, so it is safe to
 * import from the server page (`generateStaticParams`) and the client profile
 * component alike. Every helper is null-tolerant and renders only what the JSON
 * genuinely provides — no fabricated statuses, times, or points.
 */
import type {
  DriverStanding,
  MotogpData,
  RaceBlock,
  RoundDetail,
} from "@/types/motogp";

// The official MotoGP points tables, used only for the per-race "points" column
// on a rider's profile. Grand Prix pays the top 15; the Sprint pays the top 9.
const MOTOGP_FEATURE_POINTS = [25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
const MOTOGP_SPRINT_POINTS = [12, 9, 7, 6, 5, 4, 3, 2, 1];

function pointsFor(position: number, table: number[]): number {
  return position >= 1 && position <= table.length ? table[position - 1] : 0;
}

/** One driver's result for one race (sprint or feature) within a round. */
export interface DriverRaceResult {
  round: number;
  raceType: "sprint" | "feature";
  venueName: string;
  country: string | null;
  /** True once this race has an official classification. */
  completed: boolean;
  /** True when the driver was entered (appears in the race's classification). */
  entered: boolean;
  /** Model's pre-race predicted finishing position, when the driver is entered. */
  predictedPosition: number | null;
  /** Official finishing position, once classified. */
  actualPosition: number | null;
  /** Base championship points for the finish (from the MotoGP table), else null. */
  points: number | null;
  /** Entered a completed race but has no classified finish (retired / NC). */
  dnf: boolean;
}

function raceResult(
  block: RaceBlock,
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
  const table = block.raceType === "sprint" ? MOTOGP_SPRINT_POINTS : MOTOGP_FEATURE_POINTS;
  const points = actualPosition != null ? pointsFor(actualPosition, table) : null;
  const dnf = entered && completed && actualPosition == null;

  return {
    round: round.round,
    raceType: block.raceType,
    venueName: round.venueName,
    country: round.country,
    completed,
    entered,
    predictedPosition,
    actualPosition,
    points,
    dnf,
  };
}

/**
 * Both scored races for one round (sprint first, then feature) filtered to the
 * ones this driver was actually entered in.
 */
export function driverRoundResults(
  round: RoundDetail,
  code: string,
): DriverRaceResult[] {
  return [raceResult(round.sprint, round, code), raceResult(round.feature, round, code)]
    .filter((r) => r.entered);
}

/** Flatten a driver's results across every loaded round, in race order. */
export function driverSeasonResults(
  rounds: RoundDetail[],
  code: string,
): DriverRaceResult[] {
  return rounds
    .slice()
    .sort((a, b) => a.round - b.round)
    .flatMap((r) => driverRoundResults(r, code));
}

/** Reliability summary derived from a driver's classified races. */
export interface DriverReliability {
  /** Completed races the driver started (finishes + DNFs). */
  starts: number;
  /** Races finished / classified. */
  finishes: number;
  /** Races started but not classified (retired / NC). */
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

/** Best (lowest) classified finishing position across completed races. */
export function bestFinish(results: DriverRaceResult[]): number | null {
  const positions = results
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/** Count of points-paying finishes (Grand Prix top 15, Sprint top 9). */
export function pointsFinishes(results: DriverRaceResult[]): number {
  return results.filter((r) => (r.points ?? 0) > 0).length;
}

/**
 * Cumulative points-progression series for the chart, from the standings row's
 * `pointsHistory` (already cumulative per completed round). The per-round delta
 * powers the tooltip ("points scored this round").
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
export function findDriverStanding(
  drivers: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return drivers?.find((d) => d.code === code) ?? null;
}

/**
 * Enumerate every driver code known to the season (the full standings roster).
 * Used by `generateStaticParams` (server) and to validate a requested code
 * (client).
 */
export function allDriverCodes(
  data: Pick<MotogpData, "driverStandings"> | null,
): string[] {
  const codes = new Set<string>();
  data?.driverStandings?.forEach((d) => d.code && codes.add(d.code));
  return Array.from(codes);
}
