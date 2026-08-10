/**
 * Pure aggregation helpers for the /driver/[code] profile pages.
 *
 * This module is deliberately fs-free and side-effect-free so it can be
 * imported from both the server page (generateStaticParams / metadata, via the
 * fs loaders in `indycardata.ts`) and the `"use client"` profile component
 * (which re-fetches the same JSON at runtime via `indycarclient.ts`). Every
 * helper operates on already-fetched data and renders only what the JSON
 * actually provides — IndyCar ships no per-driver car number or nationality, so
 * those sections are simply absent (never fabricated).
 *
 * Data shapes come straight from `@/types/indycar`:
 *   - identity + season line  ← indycar.json `driverStandings[*]` (keyed by `code`)
 *   - points chart            ← the same row's cumulative `pointsHistory`
 *   - predicted-vs-actual     ← rounds/*.json `race.classification` (predicted
 *                               `position` + `actualPosition`) and `actualStatus`
 *   - observed reliability    ← `actualStatus` finish/DNF vocabulary
 *   - predicted retirement    ← `classification[*].pDnf` (the model's attrition head)
 */
import type {
  ClassificationEntry,
  DriverStanding,
  IndycarData,
  RoundDetail,
} from "@/types/indycar";

// ---------------------------------------------------------------------------
// Finish-status vocabulary.
//
// IndyCar's per-round `actualStatus` map is keyed by driver code. For a car
// that took the flag it holds a time / gap / lap-deficit ("1:51:06.4432",
// "+3.2", "-1 Lap"); for a car that retired it holds the retirement reason
// ("Contact", "Mechanical", "Retired", "Hybrid unit", "Lost right-rear wheel").
// A running finish is therefore anything that parses as a time-like token;
// everything else is treated as a DNF.
// ---------------------------------------------------------------------------
export function isFinisherStatus(status: string | null | undefined): boolean {
  if (status == null) return false;
  const s = status.trim().toLowerCase();
  if (s === "") return false;
  if (s === "running") return true;
  if (s.includes(":")) return true; // lap time e.g. "1:51:06.4432"
  if (s.startsWith("+")) return true; // gap e.g. "+3.2"
  if (/^-?\d+\s+laps?$/.test(s)) return true; // "-1 lap" / "-2 laps"
  if (/^\d+(\.\d+)?$/.test(s)) return true; // bare number
  return false;
}

/** One driver's result for one round — predicted vs actual, plus finish status. */
export interface DriverRoundResult {
  round: number;
  venueKey: string;
  name: string;
  raceName: string | null;
  country: string | null;
  date: string | null;
  /** Predicted finishing position (model output). Present for every round. */
  predictedPosition: number | null;
  /** Actual finishing position — only once the round has been classified. */
  actualPosition: number | null;
  /** Raw running-status string ("1:51:06.4432" / "Contact" / …), when present. */
  status: string | null;
  /** Championship points scored in the round (derived from the cumulative
   *  standings history; null when it cannot be aligned). */
  points: number | null;
  /** True when the driver started but did not finish (a retirement reason). */
  dnf: boolean;
  /** True once an official finishing position exists for this round. */
  completed: boolean;
}

/** Distil one round file into this driver's predicted-vs-actual result. */
export function driverRoundResult(
  round: RoundDetail,
  code: string,
): DriverRoundResult {
  const entry = round.race?.classification?.find((c) => c.code === code) ?? null;
  const predicted = entry?.position ?? null;
  const actualPosition = entry?.actualPosition ?? null;
  const status = round.race?.actualStatus?.[code] ?? null;
  const completed = actualPosition != null;
  const dnf = completed && status != null && !isFinisherStatus(status);

  return {
    round: round.round,
    venueKey: round.venueKey,
    name: round.venueName,
    raceName: round.raceName ?? null,
    country: round.country ?? null,
    date: round.raceDate ?? null,
    predictedPosition: predicted,
    actualPosition,
    status,
    points: null,
    dnf,
    completed,
  };
}

/**
 * Build every relevant per-round result for a driver, sorted by round, with
 * per-round championship points filled in from the cumulative `pointsHistory`.
 * The history is one cumulative total per completed round (index 0 == round 1),
 * so the round-`r` delta is `history[r-1] - history[r-2]`. Only rounds where the
 * driver actually appears (predicted or classified) are returned.
 */
export function buildDriverResults(
  rounds: RoundDetail[],
  code: string,
  history: number[] | undefined | null,
): DriverRoundResult[] {
  const results = rounds
    .map((r) => driverRoundResult(r, code))
    .filter((r) => r.predictedPosition != null || r.completed)
    .sort((a, b) => a.round - b.round);

  if (history && history.length > 0) {
    for (const r of results) {
      const idx = r.round - 1;
      if (r.completed && idx >= 0 && idx < history.length) {
        r.points = idx === 0 ? history[idx] : history[idx] - history[idx - 1];
      }
    }
  }
  return results;
}

/** Reliability summary derived from a driver's classified rounds. */
export interface DriverReliability {
  /** Rounds the driver started (a classified result exists). */
  starts: number;
  /** Rounds that ended with a running finish. */
  finishes: number;
  /** Rounds that ended in retirement. */
  dnfs: number;
  /** DNFs / starts in [0, 1], or null when no starts recorded. */
  dnfRate: number | null;
}

export function computeReliability(
  results: DriverRoundResult[],
): DriverReliability {
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

/**
 * Mean retirement risk the model assigned this driver across the rounds where
 * it published a `pDnf`. Model output — distinct from the observed DNF rate,
 * surfaced side-by-side for honesty.
 */
export function meanPredictedDnfRisk(
  entries: ClassificationEntry[],
): number | null {
  const vals = entries
    .map((e) => e.pDnf)
    .filter((v): v is number => typeof v === "number");
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/** Best (lowest) classified finishing position across finished rounds. */
export function bestFinish(results: DriverRoundResult[]): number | null {
  const positions = results
    .filter((r) => r.completed && !r.dnf)
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/** Cumulative points-progression series for the chart. */
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
export function recentForm(
  history: number[] | undefined | null,
  n = 3,
): number {
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

/** Every driver code known to the season (the standings roster). */
export function allDriverCodes(
  data: Pick<IndycarData, "driverStandings"> | null,
): string[] {
  const codes = new Set<string>();
  data?.driverStandings?.forEach((d) => d.code && codes.add(d.code));
  return Array.from(codes);
}
