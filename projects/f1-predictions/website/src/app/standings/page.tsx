import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import { Suspense } from "react";
import StandingsPage from "@/components/StandingsPage";

// ---------------------------------------------------------------------------
// Metadata only. Read at build time (static export) to produce a rich,
// title-race-aware description + the shareable OG card. The page body below is
// unchanged — StandingsPage is owned elsewhere and not touched here.
// ---------------------------------------------------------------------------
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";
const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
  } catch {
    return null;
  }
}

interface StandingsDriverMeta {
  position: number;
  driverFullName: string;
  team: string;
  points: number;
}
interface StandingsMeta {
  lastUpdatedRound?: number;
  drivers?: StandingsDriverMeta[];
}
interface SeasonMeta {
  season?: number;
  totalRounds?: number;
}

function buildStandingsMeta(): { title: string; description: string } {
  const standings = readJson<StandingsMeta>("standings.json");
  const season = readJson<SeasonMeta>("season.json");
  const year = season?.season ?? new Date().getFullYear();
  const title = `F1 ${year} Championship Standings`;

  const drivers = [...(standings?.drivers ?? [])].sort(
    (a, b) => a.position - b.position,
  );
  const leader = drivers[0];
  const runnerUp = drivers[1];
  const round = standings?.lastUpdatedRound;
  const total = season?.totalRounds;

  if (leader) {
    const gap = runnerUp ? leader.points - runnerUp.points : 0;
    const lead = gap > 0 ? ` by ${gap} points` : "";
    const roundText = round && total ? ` after Round ${round} of ${total}` : "";
    return {
      title,
      description:
        `${leader.driverFullName} leads the ${year} Formula 1 Drivers' Championship${lead}${roundText}. ` +
        "Follow the full title race — drivers and constructors — with points projected at current pace.",
    };
  }
  return {
    title,
    description:
      `Live ${year} Formula 1 Drivers' and Constructors' Championship standings, ` +
      "with points projected at current pace.",
  };
}

const { title: STANDINGS_TITLE, description: STANDINGS_DESC } =
  buildStandingsMeta();
const OG_STANDINGS = `${BASE_PATH}/og/standings.png`;

export const metadata: Metadata = {
  title: STANDINGS_TITLE,
  description: STANDINGS_DESC,
  alternates: { canonical: "/standings" },
  openGraph: {
    type: "website",
    title: STANDINGS_TITLE,
    description: STANDINGS_DESC,
    url: "/standings",
    images: [
      {
        url: OG_STANDINGS,
        width: 1200,
        height: 630,
        alt: `${STANDINGS_TITLE} — the title race`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: STANDINGS_TITLE,
    description: STANDINGS_DESC,
    images: [OG_STANDINGS],
  },
};

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[60vh] flex items-center justify-center">
          <div className="loading-pulse text-lg" style={{ color: "var(--text-muted)" }}>Loading standings...</div>
        </div>
      }
    >
      <StandingsPage />
    </Suspense>
  );
}
