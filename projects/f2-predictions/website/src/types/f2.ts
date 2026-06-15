// TypeScript mirror of the JSON produced by f2_predictions.export.build_payload().

export interface CalendarRound {
  round: number;
  key: string;
  name: string;
  country: string | null;
  completed: boolean;
}

export interface DriverStanding {
  position: number;
  code: string;
  name: string;
  team: string;
  points: number;
  wins: number;
  podiums: number;
}

export interface TeamStanding {
  position: number;
  team: string;
  points: number;
  wins: number;
  podiums: number;
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

export interface F2Data {
  sport: string;
  season: number;
  completedRounds: number;
  totalRounds: number;
  calendar: CalendarRound[];
  driverStandings: DriverStanding[];
  teamStandings: TeamStanding[];
  championship: TitleOdds[];
  nextPrediction: NextPrediction | null;
}
