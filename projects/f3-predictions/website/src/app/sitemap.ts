import type { MetadataRoute } from "next";

import { getF3Data } from "@/lib/f3data";

/**
 * sitemap.ts — generates /sitemap.xml at build time (Next.js App Router
 * convention, statically exported). Ported from the RaceIQ F1 flagship and
 * driven by f3.json. Override the site URL with NEXT_PUBLIC_SITE_URL.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://motorsportverse.org/projects/f3-predictions";

const BASE = SITE_URL.replace(/\/$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  let lastUpdated = new Date();
  let totalRounds = 14;
  let driverCodes: string[] = [];
  try {
    const data = getF3Data();
    if (data.generatedAt) lastUpdated = new Date(data.generatedAt);
    if (data.totalRounds) totalRounds = data.totalRounds;
    driverCodes = data.driverStandings.map((d) => d.code);
  } catch {
    /* fall back to defaults if f3.json is unreadable at build time */
  }

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${BASE}/`, lastModified: lastUpdated, changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE}/calendar`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/standings`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/accuracy`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.7 },
    { url: `${BASE}/about`, lastModified: lastUpdated, changeFrequency: "monthly", priority: 0.4 },
  ];

  const raceEntries: MetadataRoute.Sitemap = Array.from(
    { length: totalRounds },
    (_, i) => i + 1,
  ).map((round) => ({
    url: `${BASE}/race/${round}`,
    lastModified: lastUpdated,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  const driverEntries: MetadataRoute.Sitemap = driverCodes.map((code) => ({
    url: `${BASE}/driver/${code}`,
    lastModified: lastUpdated,
    changeFrequency: "weekly",
    priority: 0.6,
  }));

  return [...staticEntries, ...raceEntries, ...driverEntries];
}
