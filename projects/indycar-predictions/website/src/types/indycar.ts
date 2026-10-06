// TypeScript mirror of the JSON produced by indycar_predictions.export + the
// forward_eval / drift_report / promotion_decision CLIs.
//
// This is the load-bearing data contract between the Python pipeline and the
// website. Keep it in sync with tests/test_website_data_schema.py (the pydantic
// mirror) — both must change together, exactly like the F1 flagship.
//
// IndyCar weekends run ONE points race per round. The oval / road / street
// split is first-class on every surface: each round carries a `trackType`
// (the calibration stratum and the calendar badge) plus a coarser `trackGroup`
// (oval vs road_street — the model rates the two surfaces separately), and the
// Indianapolis 500 is flagged with `isIndy500` (33-car field, one-off entries).

/** IndyCar track archetype — the calibration stratum and the calendar badge. */
export type TrackType = "oval" | "road" | "street";

/** Coarse surface family — the model scores oval and road/street separately. */
export type TrackGroup = "oval" | "road_street";

/** Physical venue kind (permanent road circuit, temporary street, or oval). */
export type VenueKind = "oval" | "circuit" | "street";

// --------------------------------------------------------------------------- //
// Season summary — public/data/indycar.json
// --------------------------------------------------------------------------- //
export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  /** Marketing race title, e.g. "Firestone Grand Prix of St. Petersburg". */
  raceName?: string;
  country: string | null;
  kind: VenueKind;
  trackType: TrackType;
  trackGroup: TrackGroup;
  /** True only for the Indianapolis 500 (33-car field). */
  isIndy500?: boolean;
  city?: string;
  raceDate?: string;
  completed: boolean;
  dataSource?: string | null;
}

export interface DriverStanding {
  position: number;
  code: string;
  name: string;
  team: string;
  /** Engine supplier — Chevrolet / Honda. */
  engine?: string;
  teamColor?: string;
  points: number;
  wins: number;
  podiums: number;
  top10s?: number;
  /** Cumulative points after each completed round (real, from the data). */
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
  podiums?: number;
  pointsHistory?: number[];
}

export interface EngineStanding {
  position: number;
  engine: string;
  color: string;
  points: number;
  wins: number;
}

export interface TitleOdds {
  code: string;
  name: string;
  team: string;
  engine?: string;
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
  /** First-class DNF hazard from the model's attrition head (oval-risk aware). */
  pDnf?: number;
}

export interface NextPrediction {
  season: number;
  round: number;
  venueKey: string;
  venueName: string;
  raceName?: string;
  trackType?: TrackType;
  trackGroup?: TrackGroup;
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

export interface IndycarData {
  sport: string;
  season: number;
  seasonLabel?: string;
  generatedAt?: string;
  completedRounds: number;
  lastUpdatedRound?: number;
  totalRounds: number;
  /** Calendar composition by track archetype (oval / road / street). */
  trackTypeCounts?: Record<TrackType, number>;
  calendar: CalendarRound[];
  driverStandings: DriverStanding[];
  teamStandings: TeamStanding[];
  engineStandings?: EngineStanding[];
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
  engine?: string;
  teamColor: string;
  predictedValue: number;
  pWin: number;
  pPodium: number;
  pTop6: number;
  pTop10: number;
  /** DNF hazard for this driver at this track (attrition + oval-risk). */
  pDnf?: number;
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
  raceType: "race";
  grid: GridEntry[];
  classification: ClassificationEntry[];
  actualResults?: { position: number; code: string }[];
  /** Official running status per driver code (Running / Contact / Mechanical ...). */
  actualStatus?: Record<string, string>;
  accuracy?: RaceAccuracy;
}

/** A/B lever provenance for the finishing-position head (INDYCAR_USE_POSITION_HEAD,
 *  default OFF). Mirrors F1's `modelConfig.positionModel` block. */
export interface PositionModelConfig {
  applied: boolean;
  /** Prior completed rounds the head trained on (leakage-safe), when applied. */
  trainedRounds?: number[];
  trainRows?: number;
  /** Graceful-degradation reason when the head could not train. */
  reason?: string;
}

/** Whether the per-track DNF hazard composed into the finishing distribution. */
export interface DnfCompositionConfig {
  applied: boolean;
  reason?: string;
}

/** Which surface family's rating drove this round (oval vs road/street). */
export interface DualTrackRatingConfig {
  applied: boolean;
  group?: TrackGroup;
  reason?: string;
}

export interface RoundModelConfig {
  positionModel: PositionModelConfig;
  dnfComposition?: DnfCompositionConfig;
  dualTrackElo?: DualTrackRatingConfig;
}

export interface RoundDetail {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  raceName?: string;
  country: string | null;
  trackType: TrackType;
  trackGroup: TrackGroup;
  /** True only for the Indianapolis 500 (33-car field). */
  isIndy500?: boolean;
  raceDate?: string;
  completed: boolean;
  dataSource: string | null;
  /** Optional for older baked data; always emitted by current exports. */
  modelConfig?: RoundModelConfig;
  race: RaceBlock;
}

// --------------------------------------------------------------------------- //
// Per-round probabilities — public/data/probabilities/round_NN.json
// --------------------------------------------------------------------------- //
export interface MarketProb {
  probability: number;
  rawProbability: number;
}

export interface RaceProbabilities {
  raceType: "race";
  trackType: TrackType;
  trackGroup: TrackGroup;
  markets: Record<string, Record<string, MarketProb>>;
  /** Per-driver DNF hazard for this round. */
  dnf?: Record<string, number>;
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
  race: RaceProbabilities;
}

export interface CalibrationSummary {
  generatedAt: string;
  applied: boolean;
  trainingRounds: number;
  /** Calibration strata → markets fitted (IndyCar stratifies by track type). */
  strata?: Record<string, string[]>;
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
  trackType: TrackType;
  trackGroup?: TrackGroup;
  race: RaceAccuracy;
  /** Same race re-scored from the actual starting grid, once it is known. */
  racePostQuali?: RaceAccuracy | null;
  /** raceType ("race") → market → {brier, logLoss} (win/podium). */
  markets?: Record<string, Record<string, MarketScore>>;
  /** Naive baselines re-scored per round: lastRace + gridOrder (null pre-data). */
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
  modelPostQuali?: WalkForwardBlock | null;
  baselines: Record<string, WalkForwardBlock>;
}

export interface ForwardEvalSeason {
  season: number;
  roundsScored: number;
  meanPositionError: number | null;
  meanNdcgAt5: number | null;
  winnerHitRate: number | null;
  podiumHitRate: number | null;
  /** Walk-forward headline block (F1 parity); keyed "race" for IndyCar. */
  generatedAt?: string;
  finishersOnly?: boolean;
  scoring?: string;
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
  /** All-seasons pooled summary. */
  pooledSummary?: BacktestSeasonSummary;
  perSeason: BacktestSeasonBlock[];
  perDriver: BacktestDriverEntry[];
  markets: Record<string, MarketReliability>;
}
