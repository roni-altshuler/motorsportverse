// Default-season helper — ported from the F1 flagship's lib/season.ts.
// NOTE: NASCAR seasons are single calendar years; `season` == the label year.
import type { NascarData } from "@/types/nascar";

const envSeasonYear = process.env.NEXT_PUBLIC_NASCAR_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<NascarData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
