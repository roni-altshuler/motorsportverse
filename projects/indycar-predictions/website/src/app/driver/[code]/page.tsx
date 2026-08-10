import type { Metadata } from "next";

import DriverProfilePage from "@/components/driver/DriverProfilePage";
import { getIndycarData } from "@/lib/indycardata";
import { allDriverCodes, findStanding } from "@/lib/driverData";

// -------------------------------------------------------------------------
// Server-side data loading (filesystem, build time only) for
// generateStaticParams + metadata. The client re-fetches the same JSON at
// runtime via `useSeason()` (see DriverProfilePage), so nothing here is
// bundled into the browser.
// -------------------------------------------------------------------------

// Static export needs every dynamic segment enumerated up front. Prerender a
// page for every driver on the season standings roster.
export function generateStaticParams() {
  const data = getIndycarData();
  return allDriverCodes(data).map((code) => ({ code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: rawCode } = await params;
  const code = (rawCode || "").toUpperCase();

  const data = getIndycarData();
  const seasonYear = data.season;
  const standing = findStanding(data.driverStandings, code);
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;

  const title = `${fullName} — IndyCar ${seasonYear} Driver Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, and predicted-vs-actual results for the ${seasonYear} NTT IndyCar Series season.`
      : `${fullName}'s ${seasonYear} NTT IndyCar Series season profile: form, points progression, and predicted-vs-actual results.`;

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
