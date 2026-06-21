import { BASE_PATH } from "./data";

export interface SeasonIndexEntry {
  year: number;
  isCurrent: boolean;
  /** Path relative to the data root: "" for the current season, "seasons/<year>" for archives. */
  path: string;
  label: string;
}

export interface SeasonsIndex {
  current: number;
  available: number[];
  archived: number[];
  lastUpdated?: string;
  seasons: SeasonIndexEntry[];
}

/**
 * Load the multi-season index (seasons.json). Falls back to a single-season
 * index derived from season.json when the site predates multi-season support,
 * so older deployments keep working.
 */
export async function fetchSeasonsIndex(): Promise<SeasonsIndex> {
  try {
    const res = await fetch(`${BASE_PATH}/seasons.json`);
    if (res.ok) {
      const idx = (await res.json()) as SeasonsIndex;
      if (idx?.seasons?.length) return idx;
    }
  } catch {
    /* fall through to legacy single-season */
  }
  // Legacy fallback: derive the current season from season.json.
  let current = new Date().getFullYear();
  try {
    const res = await fetch(`${BASE_PATH}/season.json`);
    if (res.ok) {
      const s = await res.json();
      if (typeof s?.season === "number") current = s.season;
    }
  } catch {
    /* keep the calendar-year default */
  }
  return {
    current,
    available: [current],
    archived: [],
    seasons: [{ year: current, isCurrent: true, path: "", label: String(current) }],
  };
}

/** Resolve the data root for a given year using the index. */
export function basePathForYear(index: SeasonsIndex, year: number): string {
  const entry = index.seasons.find((s) => s.year === year);
  return entry && entry.path ? `${BASE_PATH}/${entry.path}` : BASE_PATH;
}
