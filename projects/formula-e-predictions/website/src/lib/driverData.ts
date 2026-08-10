/**
 * Pure aggregation helpers for the /driver/[code] profile pages (Formula E).
 *
 * Ported from the RaceIQ F1 flagship's lib/driverData.ts and adapted to
 * Formula E's real data shape:
 *   - one JSON file (fe.json) carries the calendar + driver standings;
 *   - one scored race per round (no sprint/feature split);
 *   - doubleheaders are SEPARATE rounds sharing a venue key ("London"/"London II");
 *   - each round's `classification[*]` already carries `actualPosition`, so
 *     predicted-vs-actual needs no separate result-row join;
 *   - the export publishes NO per-driver finish status (Finished/Retired/DNS)
 *     and NO retirement-risk probability, so this module deliberately omits the
 *     DNF-rate / reliability surface the F1 profile shows. It renders only what
 *     the FE data genuinely supports.
 *
 * These are pure functions over already-fetched JSON — the page component owns
 * the fetching (via `@/lib/feclient`). Nothing here imports node:fs, so it is
 * safe in the client bundle.
 */
import type {
  FEData,
  RoundDetail,
  DriverStanding,
  VenueKind,
} from "@/types/fe";

// Formula E race points table (matches the server helper in lib/fedata.ts).
const FE_RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1];

function pointsFor(position: number): number {
  return position >= 1 && position <= FE_RACE_POINTS.length
    ? FE_RACE_POINTS[position - 1]
    : 0;
}

/** One driver's result for one round — predicted vs actual. */
export interface DriverRoundResult {
  round: number;
  venueKey: string;
  venueName: string;
  venueKind: VenueKind;
  country: string | null;
  date: string | null;
  /** Predicted finishing position (model output). Present for forecast rounds. */
  predictedPosition: number | null;
  /** Actual classified finishing position — only once the round has run. */
  actualPosition: number | null;
  /** Championship race points scored (finishing position only; no bonus pts). */
  points: number | null;
  /** True once an official finishing position exists for this round. */
  completed: boolean;
  /** 1-based race index within a shared-venue doubleheader, else null. */
  dhIndex: number | null;
  /** How many rounds share this venue key (1 for a standalone weekend). */
  dhCount: number;
}

/**
 * Distil every round into this driver's predicted-vs-actual results, enriched
 * from the season calendar (venue name/kind/country/date + doubleheader index).
 * Rounds where the driver appears in neither the forecast nor the result are
 * dropped (covers reserves / mid-season debuts).
 */
export function buildDriverResults(
  data: FEData,
  rounds: RoundDetail[],
  code: string,
): DriverRoundResult[] {
  const calendar = [...data.calendar].sort((a, b) => a.round - b.round);

  const dhCountByKey: Record<string, number> = {};
  for (const c of calendar) dhCountByKey[c.key] = (dhCountByKey[c.key] ?? 0) + 1;

  // Occurrence index of each round within its shared-venue group (calendar order).
  const dhIndexByRound = new Map<number, number>();
  const running: Record<string, number> = {};
  for (const c of calendar) {
    running[c.key] = (running[c.key] ?? 0) + 1;
    dhIndexByRound.set(c.round, running[c.key]);
  }

  const roundByNum = new Map(rounds.map((r) => [r.round, r]));
  const results: DriverRoundResult[] = [];

  for (const c of calendar) {
    const rd = roundByNum.get(c.round);
    const cls = rd?.race.classification.find((e) => e.code === code) ?? null;

    // actualPosition: the classification row carries it; fall back to the
    // round's actualResults list when the row is absent.
    let actual: number | null = cls?.actualPosition ?? null;
    if (actual == null && rd?.race.actualResults) {
      actual =
        rd.race.actualResults.find((a) => a.code === code)?.position ?? null;
    }
    const predicted = cls?.position ?? null;
    if (predicted == null && actual == null) continue; // driver not in this round

    const dhCount = dhCountByKey[c.key] ?? 1;
    results.push({
      round: c.round,
      venueKey: c.key,
      venueName: rd?.venueName ?? c.name,
      venueKind: rd?.venueKind ?? c.kind,
      country: c.country ?? rd?.country ?? null,
      date: c.raceDate ?? null,
      predictedPosition: predicted,
      actualPosition: actual,
      points: actual != null ? pointsFor(actual) : null,
      completed: actual != null,
      dhIndex: dhCount > 1 ? dhIndexByRound.get(c.round) ?? null : null,
      dhCount,
    });
  }

  return results;
}

/**
 * Cumulative points-progression series for the chart, reconstructed from the
 * driver's completed race finishes. Formula E awards pole + fastest-lap bonus
 * points we cannot attribute per round, so the reconstructed curve is scaled so
 * its endpoint lands exactly on the known standings total (identical approach
 * to the server-side `getPointsProgression`) — keeping the chart honest against
 * the table.
 */
export interface PointsProgressionPoint {
  round: number;
  label: string;
  cumulative: number;
  delta: number;
}

export function driverPointsProgression(
  results: DriverRoundResult[],
  standingsTotal: number | null | undefined,
): PointsProgressionPoint[] {
  const completed = results.filter((r) => r.completed);
  if (completed.length === 0) return [];

  let running = 0;
  const raw = completed.map((r) => {
    running += r.points ?? 0;
    return { round: r.round, cumulative: running };
  });

  const lastRaw = raw[raw.length - 1].cumulative;
  const useScale =
    standingsTotal != null && standingsTotal > 0 && lastRaw > 0;
  const scale = useScale ? standingsTotal! / lastRaw : 1;

  const scaled = raw.map((p) => p.cumulative * scale);
  // Pin the endpoint exactly to the standings total.
  if (useScale) scaled[scaled.length - 1] = standingsTotal!;

  return raw.map((p, i) => ({
    round: p.round,
    label: `R${p.round}`,
    cumulative: scaled[i],
    delta: i === 0 ? scaled[0] : scaled[i] - scaled[i - 1],
  }));
}

/** Sum of the last `n` per-round point deltas — a compact recent-form signal. */
export function recentForm(progression: PointsProgressionPoint[], n = 3): number {
  return progression.slice(-n).reduce((sum, p) => sum + p.delta, 0);
}

/** Best (lowest) classified finishing position across completed rounds. */
export function bestFinish(results: DriverRoundResult[]): number | null {
  const positions = results
    .filter((r) => r.completed)
    .map((r) => r.actualPosition)
    .filter((p): p is number => p != null);
  if (positions.length === 0) return null;
  return Math.min(...positions);
}

/** Rounds the driver has an official classified result for. */
export function racesScored(results: DriverRoundResult[]): number {
  return results.filter((r) => r.completed).length;
}

/** Podium finishes (P1–P3) observed across completed rounds. */
export function podiumFinishes(results: DriverRoundResult[]): number {
  return results.filter(
    (r) => r.completed && r.actualPosition != null && r.actualPosition <= 3,
  ).length;
}

/** Find a driver's standings record by 3-letter code. */
export function findStanding(
  drivers: DriverStanding[] | undefined | null,
  code: string,
): DriverStanding | null {
  return drivers?.find((d) => d.code === code) ?? null;
}

/**
 * Enumerate every driver code known to the season (the standings roster). Used
 * both by `generateStaticParams` (server) and to validate a requested code.
 */
export function allDriverCodes(
  data: Pick<FEData, "driverStandings"> | null,
): string[] {
  const codes = new Set<string>();
  data?.driverStandings?.forEach((d) => d.code && codes.add(d.code));
  return Array.from(codes);
}
