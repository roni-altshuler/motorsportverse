import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RaceDetail } from "@/components/race-detail/RaceDetail";
import { allRoundNumbers, getCircuit, getF2Data, getProbabilities, getRound } from "@/lib/f2data";

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
  if (!round) return { title: "Round — RaceIQ F2" };
  return {
    title: `Round ${round.round}: ${round.venueName} — RaceIQ F2`,
    description: `Sprint and feature-race forecasts for the F2 ${round.venueName} round.`,
  };
}

export default async function RacePage({ params }: { params: Promise<{ round: string }> }) {
  const { round: r } = await params;
  const roundNum = Number(r);
  const round = getRound(roundNum);
  if (!round) notFound();

  const probabilities = getProbabilities(roundNum);
  const data = getF2Data();
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
      />
    </div>
  );
}
