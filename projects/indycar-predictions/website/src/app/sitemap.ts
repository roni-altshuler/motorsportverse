import type { MetadataRoute } from "next";

import { getIndycarData } from "@/lib/indycardata";

/**
 * sitemap.ts — generates /sitemap.xml at build time (Next.js App Router
 * convention, statically exported). Ported from the RaceIQ F1 flagship and
 * driven by indycar.json. Override the site URL with NEXT_PUBLIC_SITE_URL.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://motorsportverse.org/projects/indycar-predictions";

const BASE = SITE_URL.replace(/\/$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  let lastUpdated = new Date();
  let totalRounds = 17;
  try {
    const data = getIndycarData();
    if (data.generatedAt) lastUpdated = new Date(data.generatedAt);
    if (data.totalRounds) totalRounds = data.totalRounds;
  } catch {
    /* fall back to defaults if indycar.json is unreadable at build time */
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

  return [...staticEntries, ...raceEntries];
}
