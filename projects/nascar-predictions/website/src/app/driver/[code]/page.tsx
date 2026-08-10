import type { Metadata } from "next";

import DriverProfilePage from "@/components/driver/DriverProfilePage";
import { getNascarData } from "@/lib/nascardata";
import { allDriverCodes, findStanding, findChampionship } from "@/lib/driverData";

// Static export needs every dynamic segment enumerated up front. We prerender a
// page for every driver in the standings (plus anyone who only appears in the
// championship projection — reserves / part-timers).
export function generateStaticParams() {
  const data = getNascarData();
  const codes = allDriverCodes(data.driverStandings, data.championship);
  return codes.map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: rawCode } = await params;
  const code = rawCode.toUpperCase();

  const data = getNascarData();
  const seasonYear = data.season;
  const standing = findStanding(data.driverStandings, code);
  const champ = findChampionship(data.championship, code);
  const fullName = standing?.name ?? champ?.name ?? code;
  const team = standing?.team ?? champ?.team ?? null;

  const title = `${fullName} — NASCAR ${seasonYear} Driver Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, playoff outlook, and predicted-vs-actual results for the ${seasonYear} NASCAR Cup Series season.`
      : `${fullName}'s ${seasonYear} NASCAR Cup Series profile: form, points progression, playoff outlook, and predicted-vs-actual results.`;

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
