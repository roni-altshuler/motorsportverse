import type { DriverStanding } from "@/types";

/**
 * Project each driver's cumulative championship points to the end of the season
 * at their current points-per-round pace.
 *
 * pointsHistory is cumulative ([18, 47, 72, 100, 131] for ANT through R5), so
 * pace = lastCumulative / completedRoundsForThatDriver.
 *
 * Mid-season debuts are guarded via findLastIndex: a driver whose history has
 * trailing nulls (joined late) projects from their last actual round, not from
 * the season's overall round count.
 *
 * v1 limitations (intentional):
 *  - Divides by ALL completed rounds — early-season noise (weather, strategy)
 *    bleeds into the projection. v2 could use a trailing 3-race window.
 *  - Treats all remaining rounds as equally-valued, ignoring Sprint weekends.
 *  - Does not use the model's per-round win/podium probabilities.
 *
 * TODO(v2): replace pace-extrapolation with Σ p_position × points_for_position
 * sourced from website/public/data/probabilities/round_NN.json for any future
 * rounds where probabilities have been published.
 */
export function computeForecast(
  drivers: DriverStanding[],
  totalRounds: number,
): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  for (const d of drivers) {
    const hist = d.pointsHistory ?? [];
    const lastIdx = findLastNonNullIndex(hist);
    if (lastIdx < 0) {
      out[d.driver] = [];
      continue;
    }
    const last = hist[lastIdx] ?? 0;
    const completedForDriver = lastIdx + 1;
    const pace = completedForDriver > 0 ? last / completedForDriver : 0;
    const remaining = Math.max(0, totalRounds - completedForDriver);
    out[d.driver] = Array.from({ length: remaining }, (_, k) => last + pace * (k + 1));
  }
  return out;
}

function findLastNonNullIndex(arr: readonly (number | null | undefined)[]): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return i;
  }
  return -1;
}
