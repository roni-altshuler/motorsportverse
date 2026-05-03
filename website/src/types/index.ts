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
