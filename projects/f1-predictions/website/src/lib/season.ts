import { SeasonData } from "@/types";

const envSeasonYear = process.env.NEXT_PUBLIC_F1_SEASON_YEAR;

export const DEFAULT_SEASON_YEAR = Number(
  envSeasonYear || new Date().getUTCFullYear()
);

export function getSeasonYear(
  season?: Pick<SeasonData, "season"> | null
): number {
  return season?.season ?? DEFAULT_SEASON_YEAR;
}
