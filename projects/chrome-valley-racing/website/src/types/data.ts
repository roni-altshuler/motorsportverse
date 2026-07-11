// TS mirror of the JSON contract produced by `python -m chrome_valley.export`.

export interface Traits {
  grit: number;
  showboat: number;
  consistency: number;
  heart: number;
}

export interface CharacterCard {
  slug: string;
  name: string;
  number: number;
  car: string;
  hometown: string;
  role: string;
  bio: string;
  color: string;
  basePace: number;
  traits: Traits;
  affinity: Record<string, number>;
}

export interface Roster {
  league: string;
  disclaimer: string;
  characters: CharacterCard[];
}

export interface VenueCard {
  slug: string;
  name: string;
  kind: string;
  tags: string[];
  laps: number;
  chaos: number;
  pitDrama: number;
  night: boolean;
  blurb: string;
}

export interface CalendarEntry {
  round: number;
  venueSlug: string;
  venueName: string;
  kind: string;
  winnerSlug: string;
  winnerName: string;
}

export interface StandingsRow {
  position: number;
  slug: string;
  name: string;
  number: number;
  color: string;
  points: number;
  wins: number;
  podiums: number;
  dnfs: number;
}

export interface LeagueData {
  league: {
    name: string;
    tagline: string;
    trophy: string;
    disclaimer: string;
  };
  seed: number;
  season: {
    name: string;
    rounds: number;
    champion: { slug: string; name: string; points: number };
    summary: string[];
  };
  venues: VenueCard[];
  calendar: CalendarEntry[];
  standings: StandingsRow[];
}

export interface RoundResult {
  position: number;
  slug: string;
  name: string;
  number: number;
  points: number;
  lapsCompleted: number;
  dnf: boolean;
  dnfReason: string | null;
  lapsLed: number;
  gapSeconds: number | null;
}

export interface RoundEvent {
  lap: number;
  kind: string;
  slug: string;
  detail: string;
}

export interface RoundDetail {
  round: number;
  venue: { slug: string; name: string; kind: string; laps: number };
  story: string[];
  results: RoundResult[];
  events: RoundEvent[];
}
