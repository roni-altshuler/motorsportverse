import type { Metadata } from "next";
import { notFound } from "next/navigation";

import CircuitMap from "@/components/race-detail/CircuitMap";
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

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <div className="flex items-start justify-between gap-6">
        <div>
          <p className="eyebrow">
            Round {round.round} · {round.completed ? "Result + forecast" : "Upcoming forecast"}
          </p>
          <h1 className="font-display mt-2 text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
            {round.venueName}
          </h1>
          <p className="mt-2 text-[var(--ink-muted)]">
            {calRound?.country ?? round.country} · {round.completed ? "Completed" : "Upcoming"} ·
            forecasts from the F2 model on MotorsportVerse core.
          </p>
        </div>
        {geometry && (
          <div className="hidden h-28 w-40 shrink-0 sm:block" aria-hidden>
            <CircuitMap geometry={geometry} accentColor="var(--accent)" showCorners={false} />
          </div>
        )}
      </div>

      <div className="mt-10">
        <RaceDetail round={round} probabilities={probabilities} />
      </div>
    </div>
  );
}
