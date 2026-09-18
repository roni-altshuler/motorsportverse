/** Serializable, shared contract for the static race feed and its browser filters. */
export interface RaceContender {
  code: string;
  name: string;
  team: string;
  win: number;
  podium: number | null;
}
export interface RaceEvent {
  id: string;
  slug: string;
  sport: string;
  accent: string;
  round: number;
  season: number;
  name: string;
  location: string;
  date: string | null;
  completed: boolean;
  updatedAt: string | null;
  href: string;
  contenders: RaceContender[];
  session: string;
  calibrated: boolean;
}
export interface SeriesEvidence {
  slug: string;
  sport: string;
  accent: string;
  href: string;
  rounds: number;
  verdict: string;
  baseline: string | null;
  modelError: number | null;
  baselineError: number | null;
  note: string;
}
export interface RaceFeed {
  asOf: string;
  events: RaceEvent[];
  series: SeriesEvidence[];
}
export type RaceStatus = 'upcoming' | 'awaiting' | 'completed' | 'undated';
export function raceStatus(event: RaceEvent, today: string): RaceStatus {
  if (event.completed) return 'completed';
  if (!event.date) return 'undated';
  return event.date < today ? 'awaiting' : 'upcoming';
}
export function isStale(event: RaceEvent, today: string): boolean {
  if (!event.updatedAt) return true;
  const age = Date.parse(`${today}T00:00:00Z`) - Date.parse(event.updatedAt);
  return !Number.isFinite(age) || age > 14 * 86400000 || age < -86400000;
}
export function displayDate(date: string | null): string {
  if (!date) return 'Date to be confirmed';
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
    .format(new Date(`${date}T12:00:00Z`));
}
