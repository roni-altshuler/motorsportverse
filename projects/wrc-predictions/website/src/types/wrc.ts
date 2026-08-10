// TypeScript mirror of the JSON produced by the WRC predictions pipeline
// (wrc.json + per-round rounds/probabilities/forward_eval, plus the drift and
// calibration CLIs).
//
// This is the load-bearing data contract between the Python pipeline and the
// website. The WRC dataset mirrors the shared MotorsportVerse shape EXCEPT that
// a rally is a SINGLE classification per round — there is no sprint, no
// qualifying and no starting grid. Every round therefore carries a single
// `rally` block, and `surface` (gravel / tarmac / snow) is a first-class field.

// --------------------------------------------------------------------------- //
// Season summary — public/data/wrc.json
// --------------------------------------------------------------------------- //
export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  country: string | null;
  /** gravel | tarmac | snow — WRC's defining variable. */
  surface: string;
  /** Colour token for the surface chip (from the data; do not hardcode). */
  surfaceColor: string;
  /** ISO date of the rally (single date the export emits). */
  date?: string;
  completed: boolean;
  dataSource?: string | null;
}

export interface DriverStanding {
  position: number;
  code: string;
  name: string;
  /** 3-letter nationality code (real data; there are no headshots or numbers). */
  nationality?: string;
  team: string;
  teamColor?: string;
  points: number;
  wins: number;
  podiums: number;
  pointsHistory?: number[];
}

/** WRC manufacturer standing — only position/team/color/points are published
 *  (no wins, podiums, or cumulative history for manufacturers). */
export interface ManufacturerStanding {
  position: number;
  team: string;
  teamColor?: string;
  points: number;
}

/** Back-compat alias for ported markup that referenced the shared name. */
export type TeamStanding = ManufacturerStanding;

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

/** One crew's line in the next-rally forecast (win + podium probabilities). */
export interface RallyForecastEntry {
  position: number;
  code: string;
  name: string;
  team: string;
  pWin: number;
  pPodium: number;
}

export interface NextPrediction {
  season: number;
  round: number;
  venueKey: string;
  venueName: string;
  surface: string;
  surfaceColor: string;
  /** "pre" before the rally runs (there is no qualifying to condition on). */
  phase?: "pre" | "post";
  rally: RallyForecastEntry[];
}

export interface SeasonAccuracy {
  roundsScored: number;
  meanPositionError: number | null;
  podiumHitRate: number | null;
  winnerHitRate: number | null;
}

export interface WrcData {
  sport: string;
  season: number;
  generatedAt?: string;
  completedRounds: number;
  lastUpdatedRound?: number;
  totalRounds: number;
  calendar: CalendarRound[];
  driverStandings: DriverStanding[];
  manufacturerStandings: ManufacturerStanding[];
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
  nationality?: string;
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
  actualPosition: number | null;
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

/** The single scored classification for a rally (no sprint, no grid). */
export interface RallyBlock {
  surface: string;
  surfaceColor?: string;
  classification: ClassificationEntry[];
  actualResults?: { position: number; code: string }[];
  accuracy?: RaceAccuracy;
}

/** Back-compat alias for ported markup that referenced the shared name. */
export type RaceBlock = RallyBlock;

/** Ensemble-lever provenance (skill model blended with championship form). */
export interface EnsembleConfig {
  applied: boolean;
  modelWeight?: number;
}

export interface RoundModelConfig {
  ensemble?: EnsembleConfig;
  surface?: string;
}

export interface RoundDetail {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  country: string | null;
  surface: string;
  surfaceColor: string;
  date?: string;
  completed: boolean;
  dataSource: string | null;
  modelConfig?: RoundModelConfig;
  rally: RallyBlock;
}

// --------------------------------------------------------------------------- //
// Per-round probabilities — public/data/probabilities/round_NN.json
// --------------------------------------------------------------------------- //
export interface MarketProb {
  probability: number;
  rawProbability: number;
}

export interface RallyProbabilities {
  surface?: string;
  markets: Record<string, Record<string, MarketProb>>;
  h2h: Record<string, Record<string, number>>;
  method: string;
  monteCarloSamples: number;
  temperature: number;
}

/** Back-compat alias for ported markup that referenced the shared name. */
export type RaceProbabilities = RallyProbabilities;

export interface CalibrationStatus {
  applied: boolean;
  reason: string;
}

export interface ProbabilitiesRound {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  surface: string;
  surfaceColor: string;
  calibration: CalibrationStatus;
  rally: RallyProbabilities;
}

export interface CalibrationSummary {
  generatedAt: string;
  applied: boolean;
  trainingRounds: number;
  dataLimitation: string;
  perMarket: Record<string, number>;
}

// --------------------------------------------------------------------------- //
// Continuous-learning outputs (forward_eval / drift CLIs)
// --------------------------------------------------------------------------- //
/** Per-market probability quality (Brier + log-loss) for one scored rally. */
export interface MarketScore {
  brier: number | null;
  logLoss: number | null;
}

/** One re-scored baseline for a round (standings-order or last-rally). */
export interface ForwardEvalBaseline {
  score: RaceAccuracy;
  markets?: Record<string, MarketScore>;
}

export interface ForwardEvalRound {
  round: number;
  venueName: string;
  surface?: string;
  /** The rally's ranking accuracy (single classification per round). */
  rally: RaceAccuracy;
  /** market → {brier, logLoss} (win / podium). */
  markets?: Record<string, MarketScore>;
  /** baseline name → re-scored score + markets (null for round 1). */
  baselines?: Record<string, ForwardEvalBaseline | null>;
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

/** Model vs baselines walk-forward summary for the rally. */
export interface WalkForwardRaceType {
  model: WalkForwardBlock;
  baselines: Record<string, WalkForwardBlock>;
}

/** Model vs standings-order vs last-rally scores for one probability market. */
export interface BaselineComparisonMetric {
  model: number;
  standings: number;
  lastRally: number;
}

/** Honest model-vs-baseline comparison ("does the forecast beat championship form?"). */
export interface BaselineComparison {
  note: string;
  roundsScored: number;
  /** Higher-is-better skill scores (1 − Brier) for win + podium markets. */
  winBrier: BaselineComparisonMetric;
  podiumBrier: BaselineComparisonMetric;
  winnerHit: BaselineComparisonMetric;
  /** The skill model alone (before the championship-form ensemble). */
  skillOnly?: { winBrier: number; podiumBrier: number };
  beatsStandingsBaseline: boolean;
}

export interface ForwardEvalSeason {
  season: number;
  roundsScored: number;
  meanPositionError: number | null;
  meanNdcgAt5: number | null;
  winnerHitRate: number | null;
  podiumHitRate: number | null;
  generatedAt?: string;
  finishersOnly?: boolean;
  /** Walk-forward headline block, keyed by "rally". */
  walkForward?: Record<string, WalkForwardRaceType>;
  /** Ensemble model vs standings-order + last-rally baselines. */
  baselineComparison?: BaselineComparison;
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
