// Default-season helper — ported from the F1 flagship's lib/season.ts.
import type { MotogpData } from "@/types/motogp";

const envSeasonYear = process.env.NEXT_PUBLIC_MOTOGP_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<MotogpData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
