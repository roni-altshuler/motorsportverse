import type { Metadata } from "next";

import DriverProfilePage from "@/components/driver/DriverProfilePage";
import { getMotogpData } from "@/lib/motogpData";
import { allDriverCodes, findDriverStanding } from "@/lib/driverData";

// -------------------------------------------------------------------------
// Server-side data loading (filesystem) for generateStaticParams + metadata.
// These run at build time only — they are not bundled into the client, which
// re-fetches the same JSON at runtime via `useSeason()` (see DriverProfilePage).
// -------------------------------------------------------------------------
function loadData() {
  try {
    return getMotogpData();
  } catch {
    return null;
  }
}

// Static export needs every dynamic segment enumerated up front. We prerender a
// page for every driver on the season roster (the full standings list).
export function generateStaticParams() {
  const data = loadData();
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

  const data = loadData();
  const seasonYear = data?.season ?? new Date().getFullYear();
  const standing = findDriverStanding(data?.driverStandings, code);
  const fullName = standing?.name ?? code;
  const team = standing?.team ?? null;

  const title = `${fullName} — MotoGP ${seasonYear} Rider Profile`;
  const bits: string[] = [];
  if (standing?.position != null) bits.push(`P${standing.position} in the championship`);
  if (standing?.points != null) bits.push(`${standing.points} points`);
  if (team) bits.push(team);
  const description =
    bits.length > 0
      ? `${fullName}: ${bits.join(", ")}. Season form, points progression, and predicted-vs-actual results for the ${seasonYear} MotoGP season.`
      : `${fullName}'s ${seasonYear} MotoGP season profile: form, points progression, and predicted-vs-actual results.`;

  const canonical = `/rider/${code}`;

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
