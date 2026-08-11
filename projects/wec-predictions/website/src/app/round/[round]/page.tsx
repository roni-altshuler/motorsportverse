import type { Metadata } from "next";
import { notFound } from "next/navigation";

import RoundDetailView from "@/components/RoundDetailView";
import { allRoundNumbers, getRound, getWecData } from "@/lib/wecData";

export function generateStaticParams() {
  return allRoundNumbers().map((round) => ({ round: String(round) }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ round: string }>;
}): Promise<Metadata> {
  const { round } = await params;
  const detail = getRound(Number(round));
  const place = detail?.place ?? `Round ${round}`;
  return {
    title: `${place} — Round ${round} — RaceIQ WEC`,
    description: `Predicted vs actual classification and win/podium probabilities for FIA WEC Round ${round} (${place}), by class.`,
  };
}

export default async function Page({ params }: { params: Promise<{ round: string }> }) {
  const { round } = await params;
  const roundNo = Number(round);
  const detail = getRound(roundNo);
  if (!detail) notFound();

  const data = getWecData();
  const calendarRound = data.calendar.find((c) => c.round === roundNo) ?? null;

  return <RoundDetailView detail={detail} calendarRound={calendarRound} />;
}
