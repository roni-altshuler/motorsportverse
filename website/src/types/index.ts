// F1 Predictions Website – Core Types

export interface RaceCalendarEntry {
  round: number;
  name: string;
  gpKey: string;
  circuit: string;
  date: string;
  postponed?: boolean;
  originalDate?: string | null;
  rescheduledDate?: string | null;
  statusNote?: string | null;
  laps: number;
  circuitKm: number;
  circuitType: string;
  expectedStops: number;
  tyreDeg: number;
  overtaking: number;
  country: string;
  sprint: boolean;
  sprintLaps: number;
  drsZones: number;
  safetyCarLikelihood: number;
  altitudeM: number;
}

export interface DriverInfo {
  code: string;
  fullName: string;
  number: number;
  team: string;
  teamColor: string;
  /**
   * Path to a 192x192 WebP headshot relative to the website public root
   * (e.g. `/headshots/VER.webp`).  Populated at Python build time by
   * `scripts/fetch_driver_headshots.py`.  Consumers must prepend
   * `NEXT_PUBLIC_BASE_PATH` before rendering — see `DriverPortrait`.
   */
  headshotUrl?: string | null;
}

export interface TeamInfo {
  name: string;
  color: string;
  drivers: string[];
  constructorPoints2025: number;
  performanceScore: number;
}

export interface SeasonData {
  season: number;
  totalRounds: number;
  calendar: RaceCalendarEntry[];
  drivers: DriverInfo[];
  teams: TeamInfo[];
  completedRounds: number[];
  lastUpdated?: string;
  source?: string;
  sourceUrl?: string;
}

export interface ClassificationEntry {
  position: number;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  predictedTime: number;
  gap: string;
  points: number;
  confidence?: "High" | "Medium" | "Low" | string;
  finishRangeLow?: number;
  finishRangeHigh?: number;
  winProbability?: number;
  /** Bootstrap 90% prediction interval lower bound (seconds, absolute). */
  predictionIntervalLow?: number;
  /** Bootstrap 90% prediction interval upper bound (seconds, absolute). */
  predictionIntervalHigh?: number;
  /** Per-driver probability of NOT classifying (DNF) in this race. */
  dnfProbability?: number;
  /** See {@link DriverInfo.headshotUrl}. */
  headshotUrl?: string | null;
}

export interface ModelMetrics {
  r2Score: number;
  mae: number;
  maxSpread: number;
  trainingYears: number[];
  avgUncertainty?: number;
}

export interface FeatureImportance {
  feature: string;
  importance: number;
}

export interface VisualizationDetail {
  filename: string;
  title: string;
  category: "ml" | "fastf1" | "advanced" | "bettor" | "other" | string;
  description: string;
  source: "model" | "fastf1" | "advanced" | string;
}

/** Vector geometry for a circuit, produced by `generate_circuit_svg.py`.
 * All coordinates are in the normalised viewBox space (default 0..1000). */
export interface CircuitGeometry {
  /** SVG viewBox string, e.g. `"0 0 1000 1000"`. */
  viewBox: string;
  /** Closed SVG path data, e.g. `"M x0 y0 L x1 y1 …Z"`. */
  path: string;
  corners: Array<{
    number: number;
    x: number;
    y: number;
    name?: string | null;
  }>;
  /** Index ranges (into the simplified path) where DRS is enabled. */
  drsZones: Array<{ startIdx: number; endIdx: number }>;
  metresPerUnit: number;
  source: "fastf1";
  generatedAt: string;
}

export interface GrandPrixReportMiss {
  driver: string;
  team: string;
  predicted: number;
  actual: number;
  delta: number;
  absDelta: number;
}

export interface GrandPrixTeamError {
  team: string;
  meanError: number;
  drivers: number;
}

export interface GrandPrixPerformanceReport {
  round: number;
  name: string;
  comparedDrivers: number;
  meanError: number;
  medianError: number;
  exactMatches: number;
  within3: number;
  within5: number;
  winnerHit: boolean;
  podiumHits: number;
  biggestMisses: GrandPrixReportMiss[];
  teamMeanError: GrandPrixTeamError[];
}

export type WeekendSessionKey = "sprintQualifying" | "sprint" | "qualifying" | "grandPrix" | string;
export type WeekendSessionKind = "qualifying" | "race" | "sprint" | string;
export type WeekendSessionStatus = "official" | "timing" | "pending" | "unavailable" | string;

export interface WeekendFastestLap {
  rank?: number | null;
  lap?: number | null;
  time?: string | null;
  averageSpeedKph?: number | null;
}

export interface WeekendResultRow {
  position: number;
  positionText?: string;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  time?: string | null;
  gap?: string | null;
  q1?: string | null;
  q2?: string | null;
  q3?: string | null;
  points?: number;
  grid?: number | null;
  laps?: number | null;
  status?: string | null;
  fastestLap?: WeekendFastestLap;
}

export interface WeekendSessionResult {
  key: WeekendSessionKey;
  label: string;
  shortLabel: string;
  kind: WeekendSessionKind;
  status: WeekendSessionStatus;
  source: string;
  sourceUrl?: string | null;
  rows: WeekendResultRow[];
  note?: string | null;
}

export interface WeekendResultsData {
  generatedAt: string;
  source: string;
  sourceUrl?: string | null;
  loadedSessions: number;
  sessions: WeekendSessionResult[];
}

export interface RoundData {
  round: number;
  name: string;
  gpKey: string;
  circuit: string;
  date: string;
  sprint: boolean;
  sprintLaps: number;
  classification: ClassificationEntry[];
  metrics: ModelMetrics;
  featureImportance: FeatureImportance[];
  fastestLap: string;
  podium: [string, string, string];
  visualizations: string[];
  visualizationDetails?: VisualizationDetail[];
  circuitInfo: {
    type: string;
    laps: number;
    circuitKm: number;
    expectedStops: number;
    tyreDeg: number;
    overtaking: number;
    drsZones: number;
    safetyCarLikelihood: number;
    altitudeM: number;
    /** SVG vector geometry derived from FastF1 telemetry at build time.
     * Optional — circuits without telemetry yet (cold-start) fall back
     * to the matplotlib PNG. */
    geometry?: CircuitGeometry | null;
  };
  weatherData?: {
    rainProbability: number;
    temperatureC: number;
    humidity?: number | null;
    windSpeedKmh?: number | null;
    windDirection?: number | null;
    cloudCover?: number | null;
    precipitationMm?: number | null;
    weatherDescription?: string | null;
    source?: string;
  };
  telemetryData?: {
    speedTraps: SpeedTrapEntry[];
    sectorTimes: SectorTimeEntry[];
    stintTimeline?: StintTimelineEntry[];
    trackStatusEvents?: TrackStatusEvent[];
    pitStopImpact?: PitStopImpactEntry[];
    sectorDominance?: SectorDominanceEntry[];
    raceControlEvents?: RaceControlEvent[];
  };
  actualResults?: Record<string, number>;
  actualStatus?: Record<string, string>;
  weekendResults?: WeekendResultsData;
  predictionInsights?: {
    poleToWinBias: number;
    highConfidenceCount: number;
    mediumConfidenceCount: number;
    lowConfidenceCount: number;
    mostLikelyWinner: string;
    winnerProbability?: number;
    closestBattle: {
      drivers: string[];
      gap: number;
    };
  };
  accuracy?: {
    mean_position_error?: number;
    median_position_error?: number;
    exact_matches?: number;
    within_3_positions?: number;
    within_5_positions?: number;
    total_drivers?: number;
    accuracy_pct?: number;
  };
  gpReport?: GrandPrixPerformanceReport;
  generatedAt?: string;
  dataFreshness?: {
    weatherSource?: string;
    qualifyingSource?: string;
    standingsSource?: string;
    officialResultsSource?: string;
    weekendResultsSource?: string;
  };
}

export interface SpeedTrapEntry {
  driver: string;
  team: string;
  teamColor: string;
  speedKmh: number;
  sector: number;
}

export interface SectorTimeEntry {
  driver: string;
  team: string;
  teamColor: string;
  sector1: number;
  sector2: number;
  sector3: number;
  idealLap: number;
}

export interface StintSegment {
  stint: number;
  compound: string;
  startLap: number;
  endLap: number;
  laps: number;
}

export interface StintTimelineEntry {
  driver: string;
  team: string;
  teamColor: string;
  stints: StintSegment[];
}

export interface TrackStatusEvent {
  time: string;
  statusCode: string;
  statusLabel: string;
  message: string;
}

export interface PitStopImpactEntry {
  driver: string;
  team: string;
  teamColor: string;
  lap: number;
  pitTimeLoss?: number | null;
  outlapDelta: number;
}

export interface SectorDominanceEntry {
  driver: string;
  team: string;
  teamColor: string;
  sector1Rank: number;
  sector2Rank: number;
  sector3Rank: number;
  overallRank: number;
}

export interface RaceControlEvent {
  time: string;
  category: string;
  message: string;
  lap: number;
  driver?: string | null;
}

export interface WeatherForecast {
  round: number;
  gpKey: string;
  name: string;
  date: string;
  rainProbability: number;
  temperatureC: number;
  humidity: number;
  windSpeedKmh: number;
  windDirection: number;
  cloudCover: number;
  precipitationMm: number;
  weatherDescription: string;
  source: string;
  forecastDetail: {
    time: string;
    temperature_c: number;
    rain_probability: number;
    precipitation_mm: number;
    wind_speed_kmh: number;
    cloud_cover: number;
  }[];
}

export interface WeatherData {
  lastUpdated: string;
  races: WeatherForecast[];
}

export interface SeasonTrackerRound {
  round: number;
  hasActual: boolean;
  meanError: number | null;
  exactMatches: number | null;
  within3: number | null;
  accuracyPct: number | null;
}

export interface SeasonTrackerData {
  rounds: SeasonTrackerRound[];
  overallAccuracy: {
    seasonMeanError: number;
    seasonAccuracyPct: number;
    roundsWithActual: number;
  } | null;
  gpReports?: GrandPrixPerformanceReport[];
  generatedAt?: string;
}

export type RoundLifecycle =
  | "upcoming"
  | "prediction-ready"
  | "live-weekend"
  | "awaiting-results"
  | "postponed"
  | "official";

export interface DriverStanding {
  position: number;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  points: number;
  wins: number;
  podiums: number;
  pointsHistory: number[];  // cumulative per round
  /** See {@link DriverInfo.headshotUrl}. */
  headshotUrl?: string | null;
}

export interface ConstructorStanding {
  position: number;
  team: string;
  teamColor: string;
  points: number;
  wins: number;
  drivers: string[];
  pointsHistory: number[];
}

export interface StandingsData {
  lastUpdatedRound: number;
  lastUpdated?: string;
  source?: string;
  sourceUrl?: string | null;
  statusNote?: string;
  drivers: DriverStanding[];
  constructors: ConstructorStanding[];
  wdcPossibility: WDCPossibility[];
}

export interface WDCPossibility {
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  currentPoints: number;
  maxPossiblePoints: number;
  canStillWin: boolean;
}

// Country flag emoji lookup
export const COUNTRY_FLAGS: Record<string, string> = {
  "Australia": "🇦🇺", "China": "🇨🇳", "Japan": "🇯🇵",
  "Bahrain": "🇧🇭", "Saudi Arabia": "🇸🇦", "Miami": "🇺🇸",
  "Emilia Romagna": "🇮🇹", "Monaco": "🇲🇨", "Spain": "🇪🇸",
  "Canada": "🇨🇦", "Austria": "🇦🇹", "Great Britain": "🇬🇧",
  "Belgium": "🇧🇪", "Hungary": "🇭🇺", "Netherlands": "🇳🇱",
  "Italy": "🇮🇹", "Azerbaijan": "🇦🇿", "Singapore": "🇸🇬",
  "United States": "🇺🇸", "Mexico": "🇲🇽", "Brazil": "🇧🇷",
  "Las Vegas": "🇺🇸", "Qatar": "🇶🇦", "Abu Dhabi": "🇦🇪",
};

// =========================================================================
// Betting / Value Finder Types
// =========================================================================

export interface ProbabilityMarketEntry {
  driver: string;
  probability: number;
  rawProbability?: number;
}

export interface ProbabilityRoundData {
  round: number;
  season: number;
  generatedAt: string;
  method: string;
  monteCarloSamples?: number;
  temperature?: number;
  calibration: {
    method: string;
    trainingSeasons: number[];
    applied: boolean;
  };
  markets: {
    win: ProbabilityMarketEntry[];
    podium: ProbabilityMarketEntry[];
    top6: ProbabilityMarketEntry[];
    top10: ProbabilityMarketEntry[];
  };
  h2h: Record<string, Record<string, number>>;
}

export interface ValueOpportunity {
  market: string;
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  modelProbability: number;
  marketProbability: number;
  marketOdds: number;
  edgePct: number;
  kellyFraction: number;
  kellyStake: number;
  expectedValue: number;
}

export interface ValueRoundData {
  round: number;
  season: number;
  generatedAt: string;
  bookmaker: string;
  oddsTimestamp: string;
  bankrollRef: number;
  opportunities: ValueOpportunity[];
  summary: {
    totalOpportunities: number;
    positiveEdgeCount: number;
    totalKellyExposure: number;
  };
  disclaimer: string;
}

// =========================================================================
// Calibration Types
// =========================================================================

export interface ReliabilityBin {
  meanPred: number;
  empirical: number;
  count: number;
}

export interface MarketCalibrationStats {
  brierScore: number | null;
  logLoss: number | null;
  reliability: ReliabilityBin[];
  // optional fields the summary may carry — be permissive:
  uniformBaselineLogLoss?: number | null;
  nSamples?: number;
  sampleCount?: number;
}

export interface CalibrationSummary {
  generatedAt: string;
  trainingSeasons: number[];
  dataLimitation?: string;
  perMarket: Record<string, MarketCalibrationStats>;
}

// Team colors for CSS usage
export const TEAM_COLORS: Record<string, string> = {
  "Red Bull Racing": "#3671C6",
  "McLaren": "#FF8000",
  "Ferrari": "#E8002D",
  "Mercedes": "#27F4D2",
  "Aston Martin": "#229971",
  "Alpine": "#FF87BC",
  "Williams": "#64C4FF",
  "Racing Bulls": "#6692FF",
  "Haas": "#B6BABD",
  "Audi": "#1E1E1E",
  "Cadillac": "#C0C0C0",
};
