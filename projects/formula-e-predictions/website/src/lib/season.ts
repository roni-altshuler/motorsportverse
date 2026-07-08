// Default-season helper — ported from the F1 flagship's lib/season.ts.
// NOTE: Formula E seasons are split-year ("2025-26"); `season` is the END year.
import type { FEData } from "@/types/fe";

const envSeasonYear = process.env.NEXT_PUBLIC_FE_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<FEData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
