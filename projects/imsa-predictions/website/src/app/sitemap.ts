import type { MetadataRoute } from "next";

import { allEntryCodes, allRoundNumbers, getImsaData } from "@/lib/imsaData";

/**
 * sitemap.ts — generates /sitemap.xml at build time (statically exported).
 * Driven by imsa.json. Override the site URL with NEXT_PUBLIC_SITE_URL.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://motorsportverse.org/projects/imsa-predictions";

const BASE = SITE_URL.replace(/\/$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  let lastUpdated = new Date();
  let rounds: number[] = [];
  let entryCodes: string[] = [];
  try {
    const data = getImsaData();
    if (data.generatedAt) lastUpdated = new Date(data.generatedAt);
    rounds = allRoundNumbers();
    entryCodes = allEntryCodes();
  } catch {
    /* fall back to defaults if imsa.json is unreadable at build time */
  }

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${BASE}/`, lastModified: lastUpdated, changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE}/calendar`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/standings`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/predictions`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE}/accuracy`, lastModified: lastUpdated, changeFrequency: "weekly", priority: 0.7 },
    { url: `${BASE}/about`, lastModified: lastUpdated, changeFrequency: "monthly", priority: 0.4 },
  ];

  const roundEntries: MetadataRoute.Sitemap = rounds.map((round) => ({
    url: `${BASE}/round/${round}`,
    lastModified: lastUpdated,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  const entryEntries: MetadataRoute.Sitemap = entryCodes.map((code) => ({
    url: `${BASE}/entry/${code}`,
    lastModified: lastUpdated,
    changeFrequency: "weekly",
    priority: 0.6,
  }));

  return [...staticEntries, ...roundEntries, ...entryEntries];
}
