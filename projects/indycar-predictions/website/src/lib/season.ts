// Default-season helper — ported from the F1 flagship's lib/season.ts.
// NOTE: IndyCar seasons are single calendar years; `season` == the label year.
import type { IndycarData } from "@/types/indycar";

const envSeasonYear = process.env.NEXT_PUBLIC_INDYCAR_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<IndycarData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
