import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RaceDetail } from "@/components/race-detail/RaceDetail";
import { allRoundNumbers, getF2Data, getProbabilities, getRound } from "@/lib/f2data";

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

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <p className="eyebrow">
        Round {round.round} · {round.completed ? "Result + forecast" : "Upcoming forecast"}
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--ink)]">{round.venueName}</h1>
      <p className="mt-2 text-[var(--ink-muted)]">
        {calRound?.country ?? round.country} · {round.completed ? "Completed" : "Upcoming"} ·
        forecasts from the F2 model on MotorsportVerse core.
      </p>

      <div className="mt-10">
        <RaceDetail round={round} probabilities={probabilities} />
      </div>
    </div>
  );
}
