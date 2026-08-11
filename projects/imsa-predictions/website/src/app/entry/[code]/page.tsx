import type { Metadata } from "next";
import { notFound } from "next/navigation";

import EntryDetail, { type EntrySummary } from "@/components/EntryDetail";
import { allEntryCodes, allRoundNumbers, getRound, getImsaData } from "@/lib/imsaData";

export function generateStaticParams() {
  return allEntryCodes().map((code) => ({ code }));
}

export const dynamicParams = false;

function buildSummary(code: string): EntrySummary | null {
  const data = getImsaData();

  // Locate the entry within its class standings.
  let classKey = "";
  let standing: EntrySummary["standing"] | null = null;
  for (const [key, rows] of Object.entries(data.standings)) {
    const row = rows.find((r) => r.code === code);
    if (row) {
      classKey = key;
      standing = {
        position: row.position,
        points: row.points,
        wins: row.wins,
        podiums: row.podiums,
        number: row.number,
        team: row.team,
        manufacturer: row.manufacturer,
        vehicle: row.vehicle,
        drivers: row.drivers,
        teamColor: row.teamColor,
        pointsHistory: row.pointsHistory ?? [],
      };
      break;
    }
  }
  if (!standing) return null;

  const classMeta = data.classes.find((c) => c.key === classKey);
  const champEntry = data.championship[classKey]?.entries.find((e) => e.code === code) ?? null;

  // Per-round results across every published round.
  const completedRounds = data.calendar.filter((c) => c.completed).map((c) => c.round);
  const results: EntrySummary["results"] = [];
  for (const r of allRoundNumbers()) {
    const detail = getRound(r);
    if (!detail) continue;
    const block = detail.classes.find((c) => c.classification.some((e) => e.code === code));
    if (!block) continue;
    const line = block.classification.find((e) => e.code === code)!;
    const cal = data.calendar.find((c) => c.round === r);
    results.push({
      round: r,
      name: cal?.name ?? detail.place,
      country: cal?.country ?? detail.country,
      completed: detail.completed,
      predicted: line.position,
      actual: line.actualPosition,
      pWin: line.pWin,
      pPodium: line.pPodium,
      confidence: line.confidence,
    });
  }

  // Right-align points history to the completed-rounds axis.
  const n = completedRounds.length;
  const hist = standing.pointsHistory;
  const pad = Math.max(0, n - hist.length);
  const values: (number | null)[] = [
    ...Array<null>(pad).fill(null),
    ...hist.slice(Math.max(0, hist.length - n)),
  ];

  return {
    code,
    classKey,
    classLabel: classMeta?.label ?? classKey,
    classColor: classMeta?.color ?? "#999999",
    standing,
    championship: champEntry,
    progression: { rounds: completedRounds, values },
    results,
  };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const summary = buildSummary(code);
  if (!summary) return { title: "Entry — RaceIQ IMSA" };
  const s = summary.standing;
  return {
    title: `#${s.number} ${s.team} — RaceIQ IMSA`,
    description: `${summary.classLabel} entry #${s.number} ${s.team} (${s.manufacturer}) — season results, championship position, and per-round predicted vs actual finishes in the IMSA WeatherTech SportsCar Championship.`,
  };
}

export default async function Page({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const summary = buildSummary(code);
  if (!summary) notFound();
  return <EntryDetail summary={summary} />;
}
