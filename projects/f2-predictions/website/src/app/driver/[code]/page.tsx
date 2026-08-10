import type { Metadata } from "next";
import * as fs from "node:fs";
import * as path from "node:path";

import DriverProfilePage from "@/components/driver/DriverProfilePage";
import type { F2Data } from "@/types/f2";
import { allDriverCodes, findDriverStanding, findTitleOdds } from "@/lib/driverData";

// -------------------------------------------------------------------------
// Server-side data loading (filesystem) for generateStaticParams + metadata.
// These run at build time only — they are not bundled into the client, which
// re-fetches f2.json at runtime via `useSeason()` (see DriverProfilePage).
// -------------------------------------------------------------------------
const DATA_DIR = path.join(process.cwd(), "public", "data");

function loadF2Data(): F2Data | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, "f2.json"), "utf-8"),
    ) as F2Data;
  } catch {
    return null;
  }
}

// Static export needs every dynamic segment enumerated up front. We prerender a
// page for every driver on the season standings roster.
export function generateStaticParams() {
  const data = loadF2Data();
  const codes = allDriverCodes(data);
  return codes.map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: rawCode } = await params;
  const code = rawCode.toUpperCase();

  const data = loadF2Data();
  const seasonYear = data?.season ?? new Date().getFullYear();

  const standing = findDriverStanding(data?.driverStandings, code);
  const title = findTitleOdds(data?.championship, code);
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;

  const pageTitle = `${fullName} — F2 ${seasonYear} Driver Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  if (title?.pTitle != null) bits.push(`${Math.round(title.pTitle * 100)}% title chance`);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, and predicted-vs-actual results for the ${seasonYear} FIA Formula 2 season.`
      : `${fullName}'s ${seasonYear} FIA Formula 2 season profile: form, points progression, and predicted-vs-actual results.`;

  const canonical = `/driver/${code}`;

  return {
    title: pageTitle,
    description,
    alternates: { canonical },
    openGraph: { type: "profile", title: pageTitle, description, url: canonical },
    twitter: { card: "summary", title: pageTitle, description },
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
