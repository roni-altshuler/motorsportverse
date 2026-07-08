import {
  SeasonData,
  RoundData,
  StandingsData,
  WeatherData,
  SeasonTrackerData,
  RaceCalendarEntry,
  RoundLifecycle,
  ChampionshipForecast,
  ProbabilityRoundData,
  GpAccuracyReportData,
  PromotionStatusData,
} from "@/types";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";
export const BASE_PATH = PREFIX + "/data";

/**
 * Resolve the data root for a season. The active season lives at /data; an
 * archived season lives at /data/seasons/<year>. Pass the result as the `base`
 * arg to any fetcher to load a specific season (defaults to the current one).
 */
export function seasonBasePath(relativePath?: string | null): string {
  return relativePath ? `${BASE_PATH}/${relativePath}` : BASE_PATH;
}

export async function fetchSeasonData(base: string = BASE_PATH): Promise<SeasonData> {
  const res = await fetch(`${base}/season.json`);
  if (!res.ok) throw new Error("Failed to fetch season data");
  return res.json();
}

export async function fetchRoundData(round: number, base: string = BASE_PATH): Promise<RoundData> {
  const pad = round.toString().padStart(2, "0");
  const res = await fetch(`${base}/rounds/round_${pad}.json`);
  if (!res.ok) throw new Error(`Failed to fetch round ${round} data`);
  return res.json();
}

/**
 * Probability-layer output for one round (win/podium/top-6/top-10 markets +
 * head-to-head matrix). Not every round has one — returns null instead of
 * throwing so consumers can degrade gracefully.
 */
export async function fetchProbabilityData(
  round: number,
  base: string = BASE_PATH,
): Promise<ProbabilityRoundData | null> {
  try {
    const pad = round.toString().padStart(2, "0");
    const res = await fetch(`${base}/probabilities/round_${pad}.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchStandingsData(base: string = BASE_PATH): Promise<StandingsData> {
  const res = await fetch(`${base}/standings.json`);
  if (!res.ok) throw new Error("Failed to fetch standings data");
  return res.json();
}

export function getVisualizationPath(round: number, filename: string): string {
  const pad = round.toString().padStart(2, "0");
  return `${PREFIX}/visualizations/round_${pad}/${filename}`;
}

/**
 * Check which rounds have data available by trying to fetch each one.
 * Returns an array of available round numbers.
 */
export async function getAvailableRounds(totalRounds: number = 22): Promise<number[]> {
  const checks = Array.from({ length: totalRounds }, (_, i) => i + 1).map(async (r) => {
    try {
      const pad = r.toString().padStart(2, "0");
      const res = await fetch(`${BASE_PATH}/rounds/round_${pad}.json`, { method: "HEAD" });
      return res.ok ? r : null;
    } catch {
      return null;
    }
  });
  const results = await Promise.all(checks);
  return results.filter((r): r is number => r !== null);
}

export function formatLapTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(3);
  return `${mins}:${secs.padStart(6, "0")}`;
}

export function formatGap(gap: string): string {
  if (gap === "LEADER" || gap === "0.000") return "—";
  return `+${gap}s`;
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(dateStr?: string): string {
  if (!dateStr) return "Not published";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function getRaceDate(dateStr: string): Date {
  return new Date(`${dateStr}T12:00:00`);
}

export function getRoundLifecycle(
  race: Pick<RaceCalendarEntry, "date" | "sprint" | "postponed">,
  hasPrediction: boolean,
  hasActual: boolean,
  now: Date = new Date(),
): RoundLifecycle {
  if (hasActual) return "official";
  if (race.postponed) return "postponed";

  const raceDate = getRaceDate(race.date);
  const weekendStart = new Date(raceDate);
  weekendStart.setDate(raceDate.getDate() - 2);

  const syncDeadline = new Date(raceDate);
  syncDeadline.setDate(raceDate.getDate() + 1);

  if (now >= weekendStart && now <= raceDate) {
    return "live-weekend";
  }

  if (now > raceDate && now <= syncDeadline) {
    return "awaiting-results";
  }

  if (hasPrediction) {
    return "prediction-ready";
  }

  return "upcoming";
}

export function getRoundStatusMeta(status: RoundLifecycle): {
  label: string;
  shortLabel: string;
  tone: "red" | "green" | "amber" | "slate";
  description: string;
} {
  switch (status) {
    case "official":
      return {
        label: "Official Result",
        shortLabel: "Official",
        tone: "green",
        description: "Predictions are locked and compared against the classified race result.",
      };
    case "postponed":
      return {
        label: "Postponed",
        shortLabel: "Postponed",
        tone: "amber",
        description:
          "This Grand Prix has been postponed and will be updated once a new date is confirmed.",
      };
    case "live-weekend":
      return {
        label: "Grand Prix Weekend Live",
        shortLabel: "Live Weekend",
        tone: "red",
        description:
          "This race weekend is active. The page should showcase the latest forecast and live-ready analysis.",
      };
    case "awaiting-results":
      return {
        label: "Results Syncing",
        shortLabel: "Syncing",
        tone: "amber",
        description:
          "The race has run, and the site is waiting to publish the official finishing order.",
      };
    case "prediction-ready":
      return {
        label: "Prediction Published",
        shortLabel: "Prediction",
        tone: "slate",
        description: "The model forecast is available ahead of the Grand Prix weekend.",
      };
    default:
      return {
        label: "Preview Scheduled",
        shortLabel: "Upcoming",
        tone: "slate",
        description:
          "This Grand Prix is on the calendar, and the model forecast will appear before the race weekend.",
      };
  }
}

export function getStatusForRound(
  race: Pick<RaceCalendarEntry, "date" | "sprint" | "postponed">,
  hasPrediction: boolean,
  hasActual: boolean,
): RoundLifecycle {
  return getRoundLifecycle(race, hasPrediction, hasActual);
}

export function getCurrentRaceContext(
  season: SeasonData,
  roundsWithActual: number[] = [],
  now: Date = new Date(),
): {
  liveRound: RaceCalendarEntry | null;
  nextRound: RaceCalendarEntry | null;
  latestPredictionRound: RaceCalendarEntry | null;
  latestOfficialRound: RaceCalendarEntry | null;
} {
  const actualSet = new Set(roundsWithActual);
  const predictionSet = new Set(season.completedRounds);

  let liveRound: RaceCalendarEntry | null = null;
  let nextRound: RaceCalendarEntry | null = null;
  let latestPredictionRound: RaceCalendarEntry | null = null;
  let latestOfficialRound: RaceCalendarEntry | null = null;

  for (const race of season.calendar) {
    const lifecycle = getRoundLifecycle(
      race,
      predictionSet.has(race.round),
      actualSet.has(race.round),
      now,
    );

    if (lifecycle === "live-weekend") {
      liveRound = race;
    }
    if (!nextRound && getRaceDate(race.date) >= now && lifecycle !== "postponed") {
      nextRound = race;
    }
    if (predictionSet.has(race.round)) {
      latestPredictionRound = race;
    }
    if (actualSet.has(race.round)) {
      latestOfficialRound = race;
    }
  }

  return { liveRound, nextRound, latestPredictionRound, latestOfficialRound };
}

export async function fetchWeatherData(base: string = BASE_PATH): Promise<WeatherData | null> {
  try {
    const res = await fetch(`${base}/weather.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchSeasonTrackerData(
  base: string = BASE_PATH,
): Promise<SeasonTrackerData | null> {
  try {
    const res = await fetch(`${base}/season_tracker.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Season-rolling accuracy report (headline blend, winner-hit tally, and the
 * honest baselines block). Archived seasons may predate the `baselines` /
 * winner-hit fields — consumers must treat every new field as optional.
 * Returns null instead of throwing so panels can hide gracefully.
 */
export async function fetchGpAccuracyReport(
  base: string = BASE_PATH,
): Promise<GpAccuracyReportData | null> {
  try {
    const res = await fetch(`${base}/gp_accuracy_report.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/**
 * Shadow/A-B promotion decision for the candidate model stream. Only the
 * active season publishes this file — archived seasons return null and the
 * candidate panel stays hidden.
 */
export async function fetchPromotionStatus(
  base: string = BASE_PATH,
): Promise<PromotionStatusData | null> {
  try {
    const res = await fetch(`${base}/promotion_status.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchChampionshipForecast(
  base: string = BASE_PATH,
): Promise<ChampionshipForecast | null> {
  try {
    const res = await fetch(`${base}/championship_forecast.json`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
