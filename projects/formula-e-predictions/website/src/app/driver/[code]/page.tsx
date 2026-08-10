import type { Metadata } from "next";

import DriverProfilePage from "@/components/driver/DriverProfilePage";
import { getFEData } from "@/lib/fedata";
import { allDriverCodes, findStanding } from "@/lib/driverData";

// Static export needs every dynamic segment enumerated up front. We prerender a
// page for every driver on the season standings roster.
export function generateStaticParams() {
  const data = getFEData();
  return allDriverCodes(data).map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: rawCode } = await params;
  const code = rawCode.toUpperCase();
  const data = getFEData();
  const seasonYear = data.season;
  const seasonLabel = `${seasonYear - 1}-${String(seasonYear).slice(2)}`;

  const standing = findStanding(data.driverStandings, code);
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;

  const title = `${fullName} — Formula E ${seasonLabel} Driver Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, and predicted-vs-actual results for the ${seasonLabel} ABB FIA Formula E World Championship.`
      : `${fullName}'s ${seasonLabel} Formula E season profile: form, points progression, and predicted-vs-actual results.`;

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
