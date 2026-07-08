import type { Metadata } from "next";
import { notFound } from "next/navigation";

import type { WinProbabilityTrend, WinTrendSeries } from "@/components/charts/WinProbabilityChart";
import { RaceDetail } from "@/components/race-detail/RaceDetail";
import { allRoundNumbers, getCircuit, getFEData, getProbabilities, getRound } from "@/lib/fedata";
import type { FEData } from "@/types/fe";

// How many contenders the win-market trend chart follows.
const TREND_DRIVERS = 6;

/**
 * Win-market-by-round trend, built at build time from the probability files.
 *
 * Each probabilities/round_NN.json holds the win market exactly as the model
 * published it BEFORE that round (leakage-safe re-forecast), so the sequence
 * over rounds is a genuine forward-time record. Rounds beyond the next
 * upcoming one all share the same conditioning state (nothing new is known
 * about them yet), so the trend honestly stops at completedRounds + 1.
 *
 * Values are the model's win probabilities (`rawProbability` — the same
 * quantity the classification tables show as pWin); the calibrated headline
 * probability rides along for the tooltip.
 */
function buildWinTrend(data: FEData): WinProbabilityTrend | null {
  const lastRound = Math.min(data.completedRounds + 1, data.totalRounds);
  const rounds: number[] = [];
  const perRound: Array<Record<string, { probability: number; rawProbability: number }>> = [];
  for (let r = 1; r <= lastRound; r++) {
    const probs = getProbabilities(r);
    if (!probs) continue;
    rounds.push(r);
    perRound.push(probs.race.markets.win ?? {});
  }
  if (rounds.length < 2) return null;

  // Follow the strongest contenders: rank by mean pre-race win probability.
  const meanP = new Map<string, number>();
  for (const market of perRound) {
    for (const [code, m] of Object.entries(market)) {
      meanP.set(code, (meanP.get(code) ?? 0) + m.rawProbability / perRound.length);
    }
  }
  const topCodes = [...meanP.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, TREND_DRIVERS)
    .map(([code]) => code);

  const standingByCode = new Map(data.driverStandings.map((d) => [d.code, d]));
  const calibrationCollapsed = (m: { probability: number; rawProbability: number }) =>
    Math.abs(m.probability - m.rawProbability) < 1e-9;

  const series: WinTrendSeries[] = topCodes.map((code) => {
    const standing = standingByCode.get(code);
    return {
      code,
      name: standing?.name ?? code,
      color: standing?.teamColor ?? "var(--accent)",
      points: perRound.map((market) => {
        const m = market[code];
        if (!m) return { p: null };
        return {
          p: m.rawProbability,
          calibrated: calibrationCollapsed(m) ? null : m.probability,
        };
      }),
    };
  });

  return { rounds, completedRounds: data.completedRounds, series };
}

export function generateStaticParams() {
  return allRoundNumbers().map((round) => ({ round: String(round) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ round: string }>;
}): Promise<Metadata> {
  const { round: r } = await params;
  const round = getRound(Number(r));
  if (!round) return { title: "Round — RaceIQ Formula E" };
  return {
    title: `Round ${round.round}: ${round.venueName} — RaceIQ Formula E`,
    description: `Race and championship forecasts for the ${round.venueName} E-Prix.`,
  };
}

export default async function RacePage({ params }: { params: Promise<{ round: string }> }) {
  const { round: r } = await params;
  const roundNum = Number(r);
  const round = getRound(roundNum);
  if (!round) notFound();

  const probabilities = getProbabilities(roundNum);
  const data = getFEData();
  const calRound = data.calendar.find((c) => c.round === roundNum);
  const geometry = getCircuit(round.venueKey);

  // Backfill country onto the round payload from the calendar when present
  // (calendar country strings drive the flag lookup most reliably).
  const enrichedRound = { ...round, country: calRound?.country ?? round.country };

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <RaceDetail
        round={enrichedRound}
        probabilities={probabilities}
        geometry={geometry}
        driverStandings={data.driverStandings}
        championship={data.championship}
        winTrend={buildWinTrend(data)}
        calendar={data.calendar}
      />
    </div>
  );
}
