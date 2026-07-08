// Default-season helper — ported from the F1 flagship's lib/season.ts.
import type { F3Data } from "@/types/f3";

const envSeasonYear = process.env.NEXT_PUBLIC_F3_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<F3Data, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
