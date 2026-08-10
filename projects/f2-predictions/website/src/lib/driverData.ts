/**
 * Data helpers for the /driver/[code] profile pages — RaceIQ F2.
 *
 * F2's data reality differs from the F1 flagship in two ways this module has to
 * absorb, so the ported profile page stays honest:
 *   1. There is no season.json/standings.json split — everything lives in the
 *      single `f2.json` (driverStandings + calendar + championship +
 *      nextPrediction). Identity + season summary come straight off the driver's
 *      `driverStandings` row.
 *   2. Every round scores TWO races: a reversed-grid Sprint and a merit Feature.
 *      A driver therefore has up to two predicted-vs-actual rows per round.
 *
 * The F2 export ships no per-driver finish-status / DNF field and no
 * `dnfProbability`, so the reliability / retirement-risk sections of the F1
 * profile are deliberately absent here rather than faked.
 *
 * These are all pure functions over already-fetched JSON (the client page fetches
 * via `@/lib/f2client`; the server page reads the same shapes off disk), so the
 * feature is self-contained and every field is null-tolerant.
 */
import type {
  F2Data,
  DriverStanding,
  RoundDetail,
  RaceBlock,
  ClassificationEntry,
  TitleOdds,
  RaceEntry,
} from "@/types/f2";

// F2 points tables (mirror lib/f2data.ts). Used to attribute the base points a
// driver scored in a given race from the official finishing position — the F2
// export publishes the order, not per-race points. Pole / fastest-lap bonuses
// aren't attributable per-race and are not invented here.
const F2_FEATURE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1];
const F2_SPRINT_POINTS = [10, 8, 6, 5, 4, 3, 2, 1];

function basePointsFor(position: number | null, raceType: "sprint" | "feature"): number | null {
  if (position == null) return null;
  const table = raceType === "sprint" ? F2_SPRINT_POINTS : F2_FEATURE_POINTS;
  return position >= 1 && position <= table.length ? table[position - 1] : 0;
}

/** One driver's predicted-vs-actual result for one race (sprint or feature). */
export interface DriverRaceResult {
  round: number;
  /** Venue / country name, used for the header + flag lookup. */
  name: string;
  /** Country string (drives CountryFlag). */
  country: string | null;
  raceType: "sprint" | "feature";
  /** Model's pre-race finishing call (classification order). */
  predictedPosition: number | null;
  /** Official classified finishing position, once the race has run. */
  actualPosition: number | null;
  /** Base championship points for the finishing position (bonuses excluded). */
  points: number | null;
  /** True once an official finishing position exists. */
  completed: boolean;
}

function raceResult(
  round: RoundDetail,
  block: RaceBlock,
  code: string,
): DriverRaceResult | null {
  const entry = block.classification.find((c) => c.code === code);
  if (!entry) return null;
  const actualPosition = entry.actualPosition ?? null;
  return {
    round: round.round,
    name: round.venueName,
    country: round.country,
    raceType: block.raceType,
    predictedPosition: entry.position ?? null,
    actualPosition,
    points: basePointsFor(actualPosition, block.raceType),
    completed: actualPosition != null,
  };
}

/**
 * Every race (sprint + feature, in weekend order) this driver appears in, across
 * the supplied rounds, sorted by round then sprint-before-feature.
 */
export function driverRaceResults(
  rounds: RoundDetail[],
  code: string,
): DriverRaceResult[] {
  const out: DriverRaceResult[] = [];
  for (const round of rounds) {
    const sprint = raceResult(round, round.sprint, code);
    const feature = raceResult(round, round.feature, code);
    if (sprint) out.push(sprint);
    if (feature) out.push(feature);
  }
  return out.sort((a, b) =>
    a.round !== b.round
      ? a.round - b.round
      : a.raceType === b.raceType
        ? 0
        : a.raceType === "sprint"
          ? -1
          : 1,
  );
}

/** Best (lowest) classified finishing position across a set of races. */
export function bestFinish(
  results: DriverRaceResult[],
  raceType?: "sprint" | "feature",
): number | null {
  const positions = results
    .filter((r) => r.completed && (raceType ? r.raceType === raceType : true))
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/** Count of races the driver has an official classified finish in. */
export function classifiedRaces(results: DriverRaceResult[]): number {
  return results.filter((r) => r.completed).length;
}

/**
 * Mean absolute predicted-vs-actual position error across the driver's classified
 * races — the honest "how well did the model call THIS driver" number.
 */
export function meanAbsError(results: DriverRaceResult[]): number | null {
  const errs = results
    .filter((r) => r.completed && r.predictedPosition != null && r.actualPosition != null)
    .map((r) => Math.abs(r.actualPosition! - r.predictedPosition!));
  if (errs.length === 0) return null;
  return errs.reduce((a, b) => a + b, 0) / errs.length;
}

/**
 * Cumulative championship-points progression for the chart, from a driver's
 * `pointsHistory` (cumulative points after each completed round). Exposes the
 * per-round delta for the tooltip.
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

/** Find a driver's standings row by 3-letter code. */
export function findDriverStanding(
  drivers: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return drivers?.find((d) => d.code === code) ?? null;
}

/** Find a driver's title-odds row (pTitle, projected finish) by code. */
export function findTitleOdds(
  championship: TitleOdds[] | undefined | null,
  code: string,
): TitleOdds | null {
  return championship?.find((c) => c.code === code) ?? null;
}

/** Find a driver's line in the next-round feature-race forecast, by code. */
export function findNextRaceEntry(
  race: RaceEntry[] | undefined | null,
  code: string,
): RaceEntry | null {
  return race?.find((r) => r.code === code) ?? null;
}

/**
 * Every driver code known to the season — the standings roster. Used both by
 * `generateStaticParams` (server) and to validate a requested code (client).
 */
export function allDriverCodes(
  data: Pick<F2Data, "driverStandings"> | null,
): string[] {
  const codes = new Set<string>();
  data?.driverStandings?.forEach((d) => d.code && codes.add(d.code));
  return Array.from(codes);
}

/** The most relevant classification entry to explain (next unrun round's
 *  feature race, else the latest round with an entry). Used for a "why" blurb. */
export function latestFeatureEntry(
  rounds: RoundDetail[],
  code: string,
): ClassificationEntry | null {
  if (rounds.length === 0) return null;
  const next = rounds
    .filter((r) => !r.completed)
    .sort((a, b) => a.round - b.round)[0];
  const target =
    next ?? [...rounds].sort((a, b) => b.round - a.round)[0];
  return target?.feature.classification.find((c) => c.code === code) ?? null;
}
