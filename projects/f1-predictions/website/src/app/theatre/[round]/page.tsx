import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import RaceTheatre from "@/components/theatre/RaceTheatre";
import type { SeasonData } from "@/types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function loadSeason(): SeasonData | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "season.json"), "utf-8"),
    ) as SeasonData;
  } catch {
    return null;
  }
}

// Static export needs every dynamic segment enumerated up front. Mirrors the
// /race/[round] route so a Theatre page exists for every calendar round.
export function generateStaticParams() {
  return Array.from({ length: 24 }, (_, i) => ({ round: String(i + 1) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ round: string }>;
}): Promise<Metadata> {
  const { round: roundStr } = await params;
  const round = parseInt(roundStr, 10);
  const season = loadSeason();
  const entry = season?.calendar?.find((e) => e.round === round);
  const raceName = entry?.name ?? `Round ${round}`;
  const seasonYear = season?.season ?? new Date().getFullYear();

  const title = `${raceName} — Race Theatre | F1 ${seasonYear}`;
  const description =
    `Replay the ${raceName} lap by lap: all 20 cars on track, live timing tower, ` +
    `tyres, and safety-car periods — reconstructed from race telemetry.`;
  const canonical = `/theatre/${round}`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { type: "website", title, description, url: canonical },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function Page({
  params,
}: {
  params: Promise<{ round: string }>;
}) {
  const { round } = await params;
  return <RaceTheatre round={parseInt(round, 10)} />;
}
