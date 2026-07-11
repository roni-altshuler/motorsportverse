// TS mirror of the JSON written by `python -m prism_cup.export`
// (validated shape-for-shape by the project's tests/test_export.py).

export type WeightClass = "light" | "medium" | "heavy";

export interface RacerStats {
  accel: number;
  topSpeed: number;
  knockResistance: number;
  itemLuck: number;
}

export interface Racer {
  id: string;
  name: string;
  vibe: string;
  weightClass: WeightClass;
  color: string;
  bio: string;
  stats: RacerStats;
}

export interface RosterData {
  weightClasses: Record<WeightClass, { label: string; trait: string }>;
  racers: Racer[];
}

export interface Track {
  id: string;
  name: string;
  laps: number;
  hazard: number;
  boostPadDensity: number;
  color: string;
  character: string;
}

export interface TracksData {
  tracks: Track[];
}

export interface StandingRow {
  rank: number;
  racerId: string;
  name: string;
  weightClass: WeightClass;
  color: string;
  points: number;
  wins: number;
  podiums: number;
  bestFinish: number;
}

export interface ClassificationRow {
  position: number;
  racerId: string;
  name: string;
  weightClass: WeightClass;
  color: string;
  points: number;
}

export interface Highlight {
  lap: number;
  kind: string;
  text: string;
}

export interface RaceReport {
  trackId: string;
  trackName: string;
  laps: number;
  classification: ClassificationRow[];
  highlights: Highlight[];
}

export interface CupData {
  number: number;
  id: string;
  name: string;
  trackIds: string[];
  standings: StandingRow[];
  races: RaceReport[];
}

export interface Item {
  id: string;
  name: string;
  effect: string;
  rarity: "common" | "uncommon" | "rare";
  power: number;
}

export interface CupWinner {
  cup: string;
  number: number;
  winner: string;
  racerId: string;
  points: number;
}

export interface LeagueData {
  league: string;
  season: number;
  seed: number;
  disclaimer: string;
  champion: StandingRow;
  standings: StandingRow[];
  cupWinners: CupWinner[];
  cups: { number: number; id: string; name: string; trackIds: string[] }[];
  items: Item[];
  summary: {
    totalRaces: number;
    totalCups: number;
    fieldSize: number;
    uniqueWinners: number;
  };
}
