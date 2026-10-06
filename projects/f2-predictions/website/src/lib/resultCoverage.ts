/** Calendar coverage only: dates and exports never prove official availability. */
export interface CoverageRound {
  round: number;
  name: string;
  completed: boolean;
  featureDate?: string;
  raceDate?: string;
}

const GRACE_MS = 3 * 24 * 60 * 60 * 1000; // full UTC race day + 48 hours

export function resultCoverage(calendar: CoverageRound[], asOf: string) {
  const now = Date.parse(asOf);
  const imported = calendar.filter((round) => round.completed);
  const unknown: CoverageRound[] = [];
  const pastDue = calendar.filter((round) => {
    if (round.completed) return false;
    const value = round.featureDate || round.raceDate;
    const day = value && /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? Date.parse(`${value}T00:00:00Z`)
      : NaN;
    if (!Number.isFinite(day) || new Date(day).toISOString().slice(0, 10) !== value || !Number.isFinite(now)) {
      unknown.push(round);
      return false;
    }
    return now >= day + GRACE_MS;
  });
  const latest = [...imported].sort((a, b) => b.round - a.round)[0] ?? null;
  return { imported, pastDue, unknown, latest };
}

/** Dates describe the saved schedule, never whether a result is available. */
export function forecastState(round: CoverageRound, asOf: string): "completed" | "past-due" | "snapshot" | "scheduled" {
  if (round.completed) return "completed";
  const coverage = resultCoverage([round], asOf);
  if (coverage.pastDue.length) return "past-due";
  if (coverage.unknown.length) return "snapshot";
  const date = round.featureDate || round.raceDate;
  return Date.parse(asOf) >= Date.parse(`${date}T00:00:00Z`) ? "snapshot" : "scheduled";
}
