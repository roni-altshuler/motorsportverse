// TypeScript mirror of the JSON produced by the IMSA predictions pipeline
// (imsa.json + per-round rounds/probabilities, plus the calibration summary).
//
// This is the load-bearing data contract between the Python pipeline and the
// website. The IMSA dataset's defining difference from every other MotorsportVerse
// sport is that sports-car racing is MULTI-CLASS: several classes (GTP, LMP2,
// GTD PRO, GTD, …) race the same event simultaneously, each scored as its own
// classification and its own championship. Every keyed-by-class structure below
// (`standings`, `championship`, per-round `classes[]`) reflects that. The unit
// of competition is an ENTRY — a car identified by number + team + manufacturer,
// shared by a lineup of drivers — not a single driver.

// --------------------------------------------------------------------------- //
// Shared building blocks
// --------------------------------------------------------------------------- //
export interface ClassMeta {
  /** Stable class key, e.g. "GTP" | "LMP2" | "GTDPRO" | "GTD". */
  key: string;
  /** Display label, e.g. "GTP" / "GTD PRO". */
  label: string;
  /** Hex colour for the class (drives the per-class selector tint). */
  color: string;
}

export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  place: string;
  country: string | null;
  completed: boolean;
  /** Michelin Endurance Cup round (Daytona/Sebring/Watkins Glen/Petit Le Mans) —
   *  the longer races, flagged for special treatment. */
  isEnduranceCup: boolean;
  dataSource?: string | null;
}

/** One car's championship-standing line within a class. */
export interface EntryStanding {
  position: number;
  /** Unique entry code, e.g. "HYP-20" / "GT3-33" — also the /entry/[code] slug. */
  code: string;
  number: string;
  team: string;
  manufacturer: string;
  vehicle: string;
  drivers: string[];
  teamColor: string;
  points: number;
  wins: number;
  podiums: number;
  /** Cumulative points after each completed round (genuine per-round history). */
  pointsHistory: number[];
}

/** One car's line in a class title projection. */
export interface ChampionshipEntry {
  code: string;
  number: string;
  team: string;
  manufacturer: string;
  vehicle: string;
  drivers: string[];
  teamColor: string;
  pTitle: number;
  currentPoints: number;
  projMean: number;
  projP10: number;
  projP90: number;
  maxAttainable: number;
  canStillWin: boolean;
}

export interface ChampionshipClass {
  /** Human-readable basis note, e.g. "assuming a full 8-round season …". */
  basis: string;
  remainingRounds: number;
  entries: ChampionshipEntry[];
}

/** One car's line in the next-round forecast (win + podium probabilities). */
export interface NextRaceEntry {
  position: number;
  code: string;
  number: string;
  team: string;
  manufacturer: string;
  vehicle: string;
  drivers: string[];
  teamColor: string;
  pWin: number;
  pPodium: number;
}

export interface NextPredictionClass extends ClassMeta {
  race: NextRaceEntry[];
}

export interface NextPrediction {
  season: number;
  round: number;
  place: string;
  country: string | null;
  event: string;
  classes: NextPredictionClass[];
}

export interface SeasonAccuracyStat {
  roundsScored: number;
  meanPositionError: number | null;
  podiumHitRate: number | null;
  winnerHitRate: number | null;
}

export interface SeasonAccuracy {
  overall: SeasonAccuracyStat;
  /** Per-class accuracy — note this may include classes absent from `classes`
   *  (e.g. an LMP2 stratum scored on historical rounds). Always guard lookups. */
  byClass: Record<string, SeasonAccuracyStat>;
}

// --------------------------------------------------------------------------- //
// Season summary — public/data/imsa.json
// --------------------------------------------------------------------------- //
export interface ImsaData {
  sport: string;
  season: number;
  generatedAt?: string;
  completedRounds: number;
  lastUpdatedRound?: number;
  totalRounds: number;
  classes: ClassMeta[];
  calendar: CalendarRound[];
  /** class key → standings table. */
  standings: Record<string, EntryStanding[]>;
  /** class key → title projection. */
  championship: Record<string, ChampionshipClass>;
  seasonAccuracy?: SeasonAccuracy;
  nextPrediction: NextPrediction | null;
}

// --------------------------------------------------------------------------- //
// Per-round detail — public/data/rounds/round_NN.json
// --------------------------------------------------------------------------- //
export interface ClassificationEntry {
  position: number;
  code: string;
  number: string;
  team: string;
  manufacturer: string;
  vehicle: string;
  drivers: string[];
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
  /** null before the race runs (upcoming round) or when the car is unscored. */
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

export interface RoundClass extends ClassMeta {
  classification: ClassificationEntry[];
  actualResults?: { position: number; code: string }[];
  accuracy?: RaceAccuracy;
}

export interface RoundDetail {
  round: number;
  season: number;
  place: string;
  country: string | null;
  event: string;
  completed: boolean;
  dataSource: string | null;
  classes: RoundClass[];
}

// --------------------------------------------------------------------------- //
// Per-round probabilities — public/data/probabilities/round_NN.json
// --------------------------------------------------------------------------- //
export interface MarketProb {
  probability: number;
  rawProbability: number;
}

export interface ClassProbabilities extends ClassMeta {
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
  place: string;
  calibration: CalibrationStatus;
  classes: ClassProbabilities[];
}

export interface CalibrationSummary {
  generatedAt: string;
  applied: boolean;
  trainingRounds: number;
  dataLimitation: string;
}

// --------------------------------------------------------------------------- //
// Optional continuous-learning outputs (forward_eval/) — guarded everywhere,
// as the current export does not publish them. Kept permissive on purpose.
// --------------------------------------------------------------------------- //
export interface ForwardEvalBaselineVs {
  baselineWinPodiumBrier: number;
  delta: number;
  notWorse: boolean;
}

export interface ForwardEvalSeason {
  season: number;
  roundsScored?: number;
  classRoundsScored?: number;
  meanPositionError?: number | null;
  podiumHitRate?: number | null;
  winnerHitRate?: number | null;
  generatedAt?: string;
  /** Model's combined win+podium probability error vs simple baselines. */
  modelVsBaselines?: {
    modelWinPodiumBrier: number;
    vs: Record<string, ForwardEvalBaselineVs>;
  };
  [key: string]: unknown;
}
