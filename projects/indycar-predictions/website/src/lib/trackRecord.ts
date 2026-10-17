/** Winner scoring only. No ranking-error or retrospective evaluation inputs. */
export type RecordStatus = "scored" | "pending" | "missing" | "held" | "unverified" | "incomplete";
export interface RecordedPosition {
  id: string;
  name: string;
  predicted: number | null;
  actual: number | null;
}
export interface WinnerRecord {
  id: string;
  season: number;
  round: number;
  scope: string;
  scopeLabel: string;
  event: string;
  date: string | null;
  predictedWinner: string | null;
  actualWinner: string | null;
  correct: boolean | null;
  status: RecordStatus;
  reason: string;
  modelVersion: string | null;
  source: string;
  publication: string | null;
  forecastSource: string | null;
  forecastSha256: string | null;
  publicationEvent: string | null;
  sourceCommit: string | null;
  positions: RecordedPosition[];
}
export interface TrackRecordData {
  series: string;
  label: string;
  currentSeason: number;
  asOf: string;
  evaluationBasis: string | null;
  records: WinnerRecord[];
}
export interface TimelinePoint {
  date: string;
  correct: number;
  settled: number;
  accuracy: number;
  recentCorrect: number;
  recentSettled: number;
  recentAccuracy: number;
  windowStart: string;
  windowEnd: string;
  versions: string[];
}
export const ROLLING_DAYS = 28;
const DAY = 86_400_000;

export function calendarDate(value: unknown): string | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? value : null;
}

export function uniqueWinner(rows: RecordedPosition[], field: "predicted" | "actual"): string | null {
  const ids = rows.map(r => r.id);
  if (new Set(ids).size !== ids.length) return null;
  const winners = rows.filter(r => r[field] === 1);
  return winners.length === 1 ? winners[0].id : null;
}

export function selectRecords(records: WinnerRecord[], season: number, scope: string): WinnerRecord[] {
  return records.filter(r => r.season === season && r.scope === scope).slice().sort((a, b) =>
    (a.date ?? "9999").localeCompare(b.date ?? "9999") || a.round - b.round || a.id.localeCompare(b.id));
}

function scoredRecords(records: WinnerRecord[], season: number, scope: string): WinnerRecord[] {
  const selected = selectRecords(records, season, scope);
  const counts = new Map<string, number>();
  for (const row of selected) counts.set(row.id, (counts.get(row.id) ?? 0) + 1);
  return selected.filter(r => r.status === "scored" && calendarDate(r.date) !== null &&
    counts.get(r.id) === 1 && r.predictedWinner !== null && r.actualWinner !== null &&
    r.correct === (r.predictedWinner === r.actualWinner));
}

export function summarize(records: WinnerRecord[], season: number, scope: string) {
  const rows = scoredRecords(records, season, scope);
  const correct = rows.filter(r => r.correct).length;
  return { correct, settled: rows.length, accuracy: rows.length ? 100 * correct / rows.length : null };
}

/** One point per UTC event date: simultaneous races enter the denominator together. */
export function winnerTimeline(records: WinnerRecord[], season: number, scope: string): TimelinePoint[] {
  const rows = scoredRecords(records, season, scope);
  const dates = [...new Set(rows.map(r => r.date as string))].sort();
  return dates.map(date => {
    const windowStart = new Date(Date.parse(`${date}T00:00:00Z`) - (ROLLING_DAYS - 1) * DAY).toISOString().slice(0, 10);
    const cumulative = rows.filter(r => (r.date as string) <= date);
    const recent = cumulative.filter(r => (r.date as string) >= windowStart);
    const correct = cumulative.filter(r => r.correct).length;
    const recentCorrect = recent.filter(r => r.correct).length;
    return { date, correct, settled: cumulative.length, accuracy: 100 * correct / cumulative.length,
      recentCorrect, recentSettled: recent.length, recentAccuracy: 100 * recentCorrect / recent.length,
      windowStart, windowEnd: date,
      versions: [...new Set(rows.filter(r => r.date === date).flatMap(r => r.modelVersion ? [r.modelVersion] : []))].sort() };
  });
}

/** Calendar-week counts, including partial weeks; never average race percentages. */
export function winnerWeeks(records: WinnerRecord[], season: number, scope: string) {
  const weeks = new Map<string, { week: string; correct: number; settled: number }>();
  for (const row of scoredRecords(records, season, scope)) {
    const day = new Date(`${row.date}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
    const week = day.toISOString().slice(0, 10);
    const value = weeks.get(week) ?? { week, correct: 0, settled: 0 };
    value.settled += 1;
    value.correct += Number(row.correct);
    weeks.set(week, value);
  }
  return [...weeks.values()].sort((a, b) => a.week.localeCompare(b.week));
}
