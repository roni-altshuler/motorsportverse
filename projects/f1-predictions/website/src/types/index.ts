// RaceIQ Website – Core Types

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

/**
 * A single plain-language "why" factor behind a driver's predicted result.
 * Labels are user-facing (e.g. "Qualifying pace", "Recent form") — never
 * algorithm names, per the tech-stack scrub policy.
 */
export interface KeyFactor {
  /** User-facing group label, e.g. "Qualifying pace". */
  factor: string;
  /** Relative emphasis in [0, 1] (1 = this driver's strongest factor). */
  weight: number;
  /** Whether the factor helps or hurts this driver's predicted result. */
  direction: "advantage" | "risk" | "neutral";
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
  /** Top 3-4 plain-language factors behind this driver's predicted result. */
  keyFactors?: KeyFactor[];
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
  pointsHits?: number | null;
  pointsTotal?: number | null;
  podiumAccuracyPct?: number | null;
  pointsAccuracyPct?: number | null;
  accuracyPct?: number | null;
  biggestMisses: GrandPrixReportMiss[];
  teamMeanError: GrandPrixTeamError[];
}

/**
 * Provenance of the starting grid behind a round's published prediction.
 *   "real-quali-verified" — prediction frozen post-qualifying on the
 *                           round-verified official grid
 *   "estimated"           — grid estimated (qualifying not yet run or
 *                           lap times unavailable)
 *   "stale"               — grid data present but could not be re-verified
 * Open string union: additive backend values must not break the UI.
 */
export type GridProvenance = "real-quali-verified" | "estimated" | "stale" | string;

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
  /**
   * Which weekend phase the prediction was generated in.
   *   "preview"     — pre-quali; tentative outlook, qualifying not yet run
   *   "post-quali"  — qualifying complete; prediction uses real lap times
   *   "post-race"   — race classified; predicted-vs-actual comparison live
   * Optional for backwards compatibility with older round JSONs.
   */
  predictionPhase?: "preview" | "post-quali" | "post-race";
  /** True when qualifying lap times are real (not synthetic estimates). */
  qualifyingDataAvailable?: boolean;
  /** How the starting grid behind this prediction was sourced/verified.
   * Absent on pre-overhaul round JSONs and preview-phase rounds. */
  gridProvenance?: GridProvenance | null;
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
    // Headline accuracy: podium-weighted (60/40) classification over top 3 / top 10.
    accuracy_pct?: number;
    podium_hits?: number;
    podium_total?: number;
    podium_accuracy_pct?: number;
    points_hits?: number;
    points_total?: number;
    points_accuracy_pct?: number;
    // Legacy "within 3 across all drivers" kept as a detail stat.
    within_3_accuracy_pct?: number;
    // Accuracy among classified finishers (DNF/DNS excluded — attrition, not pace).
    mean_position_error_classified?: number;
    exact_matches_classified?: number;
    within_3_classified?: number;
    within_5_classified?: number;
    total_classified?: number;
    accuracy_pct_classified?: number;
    within_5_pct_classified?: number;
    dnf_count?: number;
  };
  circuitVolatility?: {
    circuit: string;
    safetyCarProbability: number;
    vscProbability: number;
    redFlagProbability: number;
    volatilityScore: number;
    nEmpirical: number;
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
  /** Which optional model paths ran for this round (A/B levers, mostly OFF). */
  modelConfig?: ModelConfig;
}

/** Records which optional model heads / levers ran when the round was
 * generated. All levers default OFF; the production path is the quali-time
 * regression. Permissive — additive fields won't break older consumers. */
export interface ModelConfig {
  lstmEnabled?: boolean;
  ensembleWeights?: Record<string, number>;
  raceSimulator?: { applied: boolean; [k: string]: unknown };
  hybridBlend?: { applied: boolean; [k: string]: unknown };
  perCircuit?: { applied: boolean; [k: string]: unknown };
  /** Direct finishing-position head (models/position_model.py). When
   * `applied`, the race order + win probabilities come from this head. */
  positionModel?: PositionModelConfig;
  [k: string]: unknown;
}

export interface PositionModelConfig {
  applied: boolean;
  /** Reason the head did not apply (e.g. too few prior rounds). */
  reason?: string;
  /** Prior rounds the head was trained on (strictly before this round). */
  trainedRounds?: number[];
  nTrainRows?: number;
  minPriorRounds?: number;
  priorRoundsAvailable?: number;
  /** Rank-correlation of the predicted order with the base pace signal
   * (healthy = positive; the head re-ranks around pace, never inverts it). */
  monotonicSanity?: number | null;
  features?: string[];
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
  podiumAccuracyPct?: number | null;
  pointsAccuracyPct?: number | null;
  within3AccuracyPct?: number | null;
  // Among classified finishers (DNF/DNS excluded).
  meanErrorClassified?: number | null;
  within3Classified?: number | null;
  accuracyPctClassified?: number | null;
  within5PctClassified?: number | null;
  dnfCount?: number | null;
}

/** Season-rolling accuracy aggregate shared by `season_tracker.json` and
 * `gp_accuracy_report.json` (`overallAccuracy` block in both). */
export interface SeasonOverallAccuracy {
  seasonMeanError: number;
  seasonAccuracyPct: number;
  seasonPodiumAccuracyPct?: number;
  seasonPointsAccuracyPct?: number;
  roundsWithActual: number;
  seasonMeanErrorClassified?: number;
  seasonAccuracyPctClassified?: number;
  seasonWithin5PctClassified?: number;
  totalDnfsExcluded?: number;
  /** Rounds where the model's predicted P1 actually won the race. */
  seasonWinnerHits?: number;
  /** seasonWinnerHits / roundsWithActual, as a percentage. */
  seasonWinnerHitPct?: number;
}

export interface SeasonTrackerData {
  rounds: SeasonTrackerRound[];
  overallAccuracy: SeasonOverallAccuracy | null;
  gpReports?: GrandPrixPerformanceReport[];
  generatedAt?: string;
}

// =========================================================================
// Honest-scoreboard types (gp_accuracy_report baselines + promotion headline)
// =========================================================================

/** Season-level stats for one naive baseline (or the model itself) in the
 * `gp_accuracy_report.json::baselines` block. Order-producing baselines
 * (grid order) carry the full set; winner-only baselines (pole-sitter,
 * points-leader) carry just the winner-hit fields. */
export interface AccuracyBaselineSeasonStats {
  roundsScored: number;
  winnerHits: number;
  winnerHitRate: number;
  podiumSetPct?: number;
  pointsSetPct?: number;
  blendPct?: number;
  meanError?: number;
}

export interface AccuracyBaselinePerRound {
  winnerHit: boolean;
  predictedWinner?: string;
  podiumHits?: number;
  podiumTotal?: number;
  top10Overlap?: number;
  meanError?: number;
  podiumAccuracyPct?: number;
  pointsAccuracyPct?: number;
  blendPct?: number;
}

export interface AccuracyBaselineBlock {
  label: string;
  description: string;
  season: AccuracyBaselineSeasonStats;
  perRound?: Record<string, AccuracyBaselinePerRound>;
}

/** `gp_accuracy_report.json::baselines` — the naive strategies the model is
 * honestly scored against. All keys optional: pre-overhaul/archived seasons
 * lack the block entirely. */
export interface AccuracyBaselines {
  gridOrder?: AccuracyBaselineBlock;
  poleSitter?: AccuracyBaselineBlock;
  pointsLeader?: AccuracyBaselineBlock;
}

/** Full schema for `gp_accuracy_report.json`. */
export interface GpAccuracyReportData {
  generatedAt?: string;
  overallAccuracy?: SeasonOverallAccuracy | null;
  gpReports?: GrandPrixPerformanceReport[];
  baselines?: AccuracyBaselines | null;
}

/** One side (production or candidate) of the promotion headline block. */
export interface PromotionHeadlineStats {
  rounds: number;
  winnerHits: number;
  winnerHitPct: number;
  podiumSetPct?: number;
  pointsSetPct?: number;
  blendPct?: number;
  meanError?: number;
}

/** `promotion_status.json::headline` — human-readable verdict of the
 * production-vs-candidate shadow comparison. */
export interface PromotionHeadline {
  roundsCompared: number;
  commonRounds?: number[];
  production: PromotionHeadlineStats;
  candidate: PromotionHeadlineStats;
  verdict: "candidate-better" | "production-better" | "parity" | string;
}

/** Schema for `promotion_status.json` (additive — snake_case fields come
 * straight from the Python promotion gate). */
export interface PromotionStatusData {
  decision: string;
  reason?: string;
  rounds_compared?: number;
  mean_production?: number;
  mean_candidate?: number;
  relative_change?: number;
  worst_round_regression?: number;
  blocked_by_per_round_guard?: boolean;
  season?: number;
  scoreKey?: string;
  headline?: PromotionHeadline | null;
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

/**
 * Output of the Monte Carlo championship simulator
 * (`championship_simulator.py`).  Consumed by the WDC + WCC tabs on
 * the standings page.
 */
export interface ChampionshipForecast {
  wdcForecast: WdcForecastEntry[];
  wccForecast: WccForecastEntry[];
  remainingRounds: number;
  remainingRoundList: { round: number; name: string; sprint: boolean }[];
  monteCarloSamples: number;
  skillSourceRound: number | null;
  lastCompletedRound: number;
  status: "ok" | "season_complete";
  note?: string;
  generatedAt?: string;
}

export interface WdcForecastEntry {
  driver: string;
  driverFullName: string;
  team: string;
  teamColor: string;
  currentPoints: number;
  championshipWinProbability: number;
  expectedFinalPoints: number;
  expectedFinalPosition: number;
  p5thPercentilePoints: number;
  p95thPercentilePoints: number;
}

export interface WccForecastEntry {
  team: string;
  teamColor: string;
  currentPoints: number;
  championshipWinProbability: number;
  expectedFinalPoints: number;
  p5thPercentilePoints: number;
  p95thPercentilePoints: number;
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

/**
 * TrustStats — build-time-derived, honest credibility numbers surfaced on the
 * marketing layer (home TrustBand + TechnicalCredibility). Assembled in
 * `lib/loadTrustStats.ts` from `benchmark/summary.json`,
 * `historical_backtest/summary.json` and `gp_accuracy_report.json`.
 *
 * NOT a Python→JSON output contract — this is a presentation-only aggregate,
 * so it has no pydantic mirror in test_website_data_schema.py. The honesty
 * rule (never blend backtest and current-season into one number) is encoded by
 * keeping the two groups structurally separate.
 *
 * Rates are stored as fractions in [0,1]; format at the render site.
 */
export interface TrustStats {
  /** Out-of-sample backtest across prior completed seasons. */
  backtest: {
    rounds: number;
    seasons: number[];
    maePositions: number;
    within3Rate: number;
    podiumHitRate: number;
    winnerHitRate: number;
    ndcgAt5: number;
    /** Fractional MAE improvement over the qualifying-pace baseline. */
    maeImprovementVsBaseline: number;
    /** Graded driver-rows behind the backtest. */
    gradedRows: number;
  } | null;
  /** Live current-season grading so far — never blended with the backtest. */
  currentSeason: {
    accuracyPct: number | null;
    roundsGraded: number;
    meanError: number | null;
  } | null;
  /** Freshness / provenance metadata for the credibility section. */
  provenance: {
    generatedAt: string | null;
  };
}

/** Per-metric walk-forward aggregation (from motorsport_core.eval). */
export interface WalkForwardMetric {
  mean: number;
  median: number;
  min: number;
  max: number;
  last: number;
  /** OLS slope across rounds; positive = metric rising over the season. */
  trend: number | null;
  n: number;
}

export interface WalkForwardBlock {
  n_rounds: number;
  metrics: Record<string, WalkForwardMetric>;
}

/** Schema for `forward_eval/summary.json` — the headline season-level
 * validation surface. Model vs baseline walk-forward, side-by-side. */
export interface ForwardEvalSummaryData {
  season: number;
  generatedAt: string;
  roundsEvaluated: number;
  walkForward: {
    model: WalkForwardBlock;
    baselines: Record<string, WalkForwardBlock>;
  };
}

/** One round of the direct-position-model A/B backtest. */
export interface PositionModelABRound {
  round: number;
  production: Record<string, unknown>;
  positionModel: Record<string, unknown> & { applied: boolean };
}

/** Schema for `forward_eval/position_model_ab.json` — walk-forward A/B of the
 * direct finishing-position head vs the production path. */
export interface PositionModelABData {
  season: number;
  generatedAt: string | null;
  minPriorRounds: number;
  roundsScored: number;
  roundsCompared: number;
  rounds: PositionModelABRound[];
  walkForward: {
    positionModel: WalkForwardBlock;
    production: WalkForwardBlock;
  };
  verdict: {
    recommendation: string;
    positionModelMeanError?: number | null;
    productionMeanError?: number | null;
    meanErrorDelta?: number | null;
    positionModelWinnerHitRate?: number | null;
    productionWinnerHitRate?: number | null;
    reason?: string;
  };
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
