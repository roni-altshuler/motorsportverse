// TypeScript mirror of the JSON produced by f2_predictions.export + the
// forward_eval / drift_report / promotion_decision CLIs.
//
// This is the load-bearing data contract between the Python pipeline and the
// website. Keep it in sync with tests/test_website_data_schema.py (the pydantic
// mirror) — both must change together, exactly like the F1 flagship.

// --------------------------------------------------------------------------- //
// Season summary — public/data/f2.json
// --------------------------------------------------------------------------- //
export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  country: string | null;
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
  qualifying: QualiEntry[];
  race: RaceEntry[];
}

export interface SeasonAccuracy {
  roundsScored: number;
  meanPositionError: number | null;
  podiumHitRate: number | null;
  winnerHitRate: number | null;
}

export interface F2Data {
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

export interface RoundDetail {
  round: number;
  season: number;
  venueKey: string;
  venueName: string;
  country: string | null;
  completed: boolean;
  dataSource: string;
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
export interface ForwardEvalRound {
  round: number;
  venueName: string;
  sprint: RaceAccuracy;
  feature: RaceAccuracy;
}

export interface ForwardEvalSeason {
  season: number;
  roundsScored: number;
  meanPositionError: number | null;
  meanNdcgAt5: number | null;
  winnerHitRate: number | null;
  podiumHitRate: number | null;
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

export interface PromotionStatus {
  decision: "promote" | "hold" | "demote";
  reason: string;
  roundsCompared: number;
  meanProduction: number | null;
  meanCandidate: number | null;
  relativeChange: number | null;
  hasCandidate: boolean;
}
