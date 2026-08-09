import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import DriverProfilePage from "@/components/driver/DriverProfilePage";
import type { SeasonData, StandingsData } from "@/types";
import { allDriverCodes, findStanding } from "@/lib/driverData";

// -------------------------------------------------------------------------
// Server-side data loading (filesystem) for generateStaticParams + metadata.
// These run at build time only — they are not bundled into the client, which
// re-fetches the same JSON at runtime via `useSeason()` (see DriverProfilePage).
// -------------------------------------------------------------------------
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

function loadStandings(): StandingsData | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "standings.json"), "utf-8"),
    ) as StandingsData;
  } catch {
    return null;
  }
}

// Static export needs every dynamic segment enumerated up front. We prerender a
// page for every driver on the season roster plus anyone in the standings
// (covers mid-season debuts / reserves).
export function generateStaticParams() {
  const season = loadSeason();
  const standings = loadStandings();
  const codes = allDriverCodes(season, standings);
  if (codes.length === 0) {
    // Nothing to enumerate — emit no params rather than a broken route.
    return [];
  }
  return codes.map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: rawCode } = await params;
  const code = rawCode.toUpperCase();

  const season = loadSeason();
  const standings = loadStandings();
  const seasonYear = season?.season ?? new Date().getFullYear();

  const info = season?.drivers?.find((d) => d.code === code);
  const standing = findStanding(standings?.drivers, code);
  const fullName = info?.fullName ?? standing?.driverFullName ?? code;
  const team = info?.team ?? standing?.team ?? null;

  const title = `${fullName} — F1 ${seasonYear} Driver Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, and predicted-vs-actual results for the ${seasonYear} Formula 1 season.`
      : `${fullName}'s ${seasonYear} Formula 1 season profile: form, points progression, and predicted-vs-actual results.`;

  const canonical = `/driver/${code}`;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      type: "profile",
      title,
      description,
      url: canonical,
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
  };
}

export default async function Page({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return <DriverProfilePage code={code} />;
}
