// TypeScript mirror of the JSON produced by f3_predictions.export + the
// forward_eval / drift_report / promotion_decision CLIs.
//
// This is the load-bearing data contract between the Python pipeline and the
// website. Keep it in sync with tests/test_website_data_schema.py (the pydantic
// mirror) — both must change together, exactly like the F1 flagship.

// --------------------------------------------------------------------------- //
// Season summary — public/data/f3.json
// --------------------------------------------------------------------------- //
export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  country: string | null;
  city?: string;
  sprintDate?: string;
  featureDate?: string;
  completed: boolean;
  dataSource?: string | null;
}

export interface DriverStanding {
  position: number;
  code: string;
  name: string;
  team: string;
  teamColor?: string;
  points: number;
  wins: number;
  podiums: number;
  pointsHistory?: number[];
  /** Optional per-driver headshot override; falls back to /headshots/<CODE>.webp. */
  headshotUrl?: string | null;
}

export interface TeamStanding {
  position: number;
  team: string;
  teamColor?: string;
  points: number;
  wins: number;
  podiums: number;
  pointsHistory?: number[];
}

export interface TitleOdds {
  code: string;
  name: string;
  team: string;
  pTitle: number;
  currentPoints: number;
  projMean: number;
  projP10: number;
  projP90: number;
  maxAttainable?: number;
  canStillWin?: boolean;
}

export interface QualiEntry {
  position: number;
  code: string;
  name: string;
  team: string;
}

export interface RaceEntry extends QualiEntry {
  pWin: number;
  pPodium: number;
}

export interface NextPrediction {
  season: number;
  round: number;
  venueKey: string;
  venueName: string;
  /** "post-quali" once real qualifying is published (grid is the actual order),
   *  else "pre" (predicted merit grid). Mirrors the F1 flagship's weekend phase. */
  phase?: "pre" | "post-quali";
  /** True when `qualifying` is the real, scraped grid rather than the predicted one. */
  qualifyingActual?: boolean;
  qualifying: QualiEntry[];
  race: RaceEntry[];
}

export interface SeasonAccuracy {
  roundsScored: number;
  meanPositionError: number | null;
  podiumHitRate: number | null;
  winnerHitRate: number | null;
}

export interface F3Data {
  sport: string;
  season: number;
  generatedAt?: string;
  completedRounds: number;
  lastUpdatedRound?: number;
  totalRounds: number;
  calendar: CalendarRound[];
  driverStandings: DriverStanding[];
  teamStandings: TeamStanding[];
  championship: TitleOdds[];
  seasonAccuracy?: SeasonAccuracy;
  nextPrediction: NextPrediction | null;
}

// --------------------------------------------------------------------------- //
// Per-round detail — public/data/rounds/round_NN.json
// --------------------------------------------------------------------------- //
export interface ClassificationEntry {
  position: number;
  code: string;
  name: string;
  team: string;
  teamColor: string;
  predictedValue: number;
  pWin: number;
  pPodium: number;
  pTop6: number;
  pTop10: number;
  meanFinish: number;
  finishRangeLow: number;
  finishRangeHigh: number;
  confidence: string;
  headshotUrl: string;
  actualPosition: number | null;
}

export interface GridEntry {
  position: number;
  code: string;
  name: string;
  team: string;
}

export interface RaceAccuracy {
  n: number;
  mean_position_error?: number;
  winner_hit?: boolean;
  podium_hits?: number;
  within_3?: number;
  within_5?: number;
  exact_matches?: number;
  spearman_correlation?: number | null;
  ndcg_at_5?: number | null;
}

export interface RaceBlock {
  raceType: "sprint" | "feature";
  grid: GridEntry[];
  classification: ClassificationEntry[];
  actualResults?: { position: number; code: string }[];
  accuracy?: RaceAccuracy;
}

/** A/B lever provenance for the finishing-position head (F3_USE_POSITION_HEAD,
 *  default OFF). Mirrors F1's `modelConfig.positionModel` block. */
export interface PositionModelConfig {
  applied: boolean;
  /** Prior completed rounds the head trained on (leakage-safe), when applied. */
  trainedRounds?: number[];
  trainRows?: number;
  /** Graceful-degradation reason when the head could not train. */
  reason?: string;
}

export interface RoundModelConfig {
  positionModel: PositionModelConfig;
}

export interface RoundDetail {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  country: string | null;
  completed: boolean;
  dataSource: string;
  /** Optional for older baked data; always emitted by current exports. */
  modelConfig?: RoundModelConfig;
  sprint: RaceBlock;
  feature: RaceBlock;
}

// --------------------------------------------------------------------------- //
// Per-round probabilities — public/data/probabilities/round_NN.json
// --------------------------------------------------------------------------- //
export interface MarketProb {
  probability: number;
  rawProbability: number;
}

export interface RaceProbabilities {
  raceType: "sprint" | "feature";
  markets: Record<string, Record<string, MarketProb>>;
  h2h: Record<string, Record<string, number>>;
  method: string;
  monteCarloSamples: number;
  temperature: number;
}

export interface CalibrationStatus {
  applied: boolean;
  reason: string;
}

export interface ProbabilitiesRound {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  calibration: CalibrationStatus;
  sprint: RaceProbabilities;
  feature: RaceProbabilities;
}

export interface CalibrationSummary {
  generatedAt: string;
  applied: boolean;
  trainingRounds: number;
  dataLimitation: string;
  perMarket: Record<string, number>;
}

// --------------------------------------------------------------------------- //
// Continuous-learning outputs (forward_eval / drift / promotion CLIs)
// --------------------------------------------------------------------------- //
/** Per-market probability quality (Brier + log-loss) for one scored race. */
export interface MarketScore {
  brier: number | null;
  logLoss: number | null;
}

export interface ForwardEvalRound {
  round: number;
  venueName: string;
  sprint: RaceAccuracy;
  feature: RaceAccuracy;
  /** Additive: raceType → market → {brier, logLoss} (win/podium). */
  markets?: Record<string, Record<string, MarketScore>>;
  /** Additive: last-race baseline re-scored, per race type (null for round 1). */
  baselines?: Record<string, RaceAccuracy | null>;
}

/** One metric's walk-forward summary (mean/median/min/max/last/trend over rounds). */
export interface WalkForwardMetric {
  mean: number;
  median: number;
  min: number;
  max: number;
  last: number;
  trend: number;
  n: number;
}

export interface WalkForwardBlock {
  n_rounds: number;
  metrics: Record<string, WalkForwardMetric>;
}

/** Model vs baselines walk-forward summary for one race type. */
export interface WalkForwardRaceType {
  model: WalkForwardBlock;
  baselines: Record<string, WalkForwardBlock>;
}

export interface ForwardEvalSeason {
  season: number;
  roundsScored: number;
  meanPositionError: number | null;
  meanNdcgAt5: number | null;
  winnerHitRate: number | null;
  podiumHitRate: number | null;
  /** Additive: walk-forward headline block (F1 parity), race type → summary. */
  generatedAt?: string;
  finishersOnly?: boolean;
  walkForward?: Record<string, WalkForwardRaceType>;
}

export interface FeatureDrift {
  feature: string;
  psi: number;
  severity: "ok" | "warn" | "alarm";
}

export interface OutputDrift {
  rollingBrierRecent: number | null;
  rollingBrierBaseline: number | null;
  relativeChange: number | null;
  severity: "ok" | "warn" | "alarm";
  roundsCompared: number;
}

export interface ModelHealth {
  season: number;
  lastEvaluatedRound: number | null;
  featureDrift: FeatureDrift[];
  outputDrift: OutputDrift | null;
  warnings: string[];
  alarms: string[];
  brierByRound: { round: number; brier: number }[];
}

/** Position-head A/B verdict (additive to promotion_status.json). */
export interface AbVerdict {
  recommendation: string;
  basis: string;
  positionHeadMeanError: number | null;
  productionMeanError: number | null;
  meanErrorDelta: number | null;
  positionHeadWinnerHitRate: number | null;
  productionWinnerHitRate: number | null;
}

export interface PromotionStatus {
  decision: "promote" | "hold" | "demote";
  reason: string;
  roundsCompared: number;
  meanProduction: number | null;
  meanCandidate: number | null;
  relativeChange: number | null;
  hasCandidate: boolean;
  /** Additive: which candidate model + its env flag, from the position-head A/B. */
  candidate?: string;
  candidateFlag?: string;
  abVerdict?: AbVerdict | null;
}

// --------------------------------------------------------------------------- //
// Historical backtest — public/data/historical_backtest/summary.json
// --------------------------------------------------------------------------- //
export interface BacktestMiss {
  driver: string;
  predicted: number;
  actual: number;
  delta: number;
  absDelta: number;
}

export interface BacktestRoundEntry {
  round: number;
  venueName: string;
  drivers_compared: number;
  mean_position_error: number | null;
  median_position_error: number | null;
  rmse_position_error: number | null;
  exact_matches: number;
  within_3: number;
  within_5: number;
  winner_hit: boolean;
  podium_hits: number;
  spearman_correlation: number | null;
  ndcg_at_5: number | null;
  biggest_misses?: BacktestMiss[];
}

export interface BacktestSeasonSummary {
  rounds_evaluated: number;
  season_mean_error: number | null;
  season_median_error: number | null;
  winner_hit_rate: number | null;
  podium_hit_rate: number | null;
  exact_match_rate: number | null;
  within_3_rate: number | null;
  within_5_rate: number | null;
  mean_spearman: number | null;
  mean_ndcg_at_5: number | null;
}

export interface BacktestSeasonBlock {
  season: number;
  summary: BacktestSeasonSummary;
  rounds: BacktestRoundEntry[];
}

export interface BacktestDriverEntry {
  driver: string;
  rounds: number;
  mae: number;
  within_3_rate: number;
}

export interface ReliabilityBin {
  binLo: number;
  binHi: number;
  meanPred: number;
  empirical: number;
  count: number;
}

export interface MarketReliability {
  brier: number | null;
  logLoss: number | null;
  samples: number;
  reliability: ReliabilityBin[];
  plot: string;
}

export interface HistoricalBacktest {
  season: number;
  seasons: number[];
  generatedAt: string;
  source: string;
  scoring: string;
  finishersOnly: boolean;
  roundsEvaluated: number;
  totalRows: number;
  perSeason: BacktestSeasonBlock[];
  perDriver: BacktestDriverEntry[];
  markets: Record<string, MarketReliability>;
}
