// Default-season helper — ported from the F1 flagship's lib/season.ts.
import type { WrcData } from "@/types/wrc";

const envSeasonYear = process.env.NEXT_PUBLIC_WRC_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<WrcData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
