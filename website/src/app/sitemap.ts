import type { MetadataRoute } from "next";
import * as fs from "node:fs";
import * as path from "node:path";
import type { SeasonData } from "@/types";

/**
 * sitemap.ts — generates /sitemap.xml at build time.
 *
 * Next.js 16 App Router convention. Statically exported as `out/sitemap.xml`.
 *
 * The site URL is configured via `NEXT_PUBLIC_SITE_URL`. For GitHub Pages
 * the default is the repo URL; override locally if needed.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://roni-altshuler.github.io/f1_predictions";

// Strip trailing slash for clean concatenation
const BASE = SITE_URL.replace(/\/$/, "");

function loadSeason(): SeasonData | null {
  try {
    const file = path.join(process.cwd(), "public", "data", "season.json");
    return JSON.parse(fs.readFileSync(file, "utf-8")) as SeasonData;
  } catch {
    return null;
  }
}

export default function sitemap(): MetadataRoute.Sitemap {
  const season = loadSeason();
  const lastUpdated = season?.lastUpdated
    ? new Date(season.lastUpdated)
    : new Date();
  const totalRounds = season?.totalRounds ?? 22;

  const staticEntries: MetadataRoute.Sitemap = [
    {
      url: `${BASE}/`,
      lastModified: lastUpdated,
      changeFrequency: "daily",
      priority: 1.0,
    },
    {
      url: `${BASE}/calendar`,
      lastModified: lastUpdated,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${BASE}/standings`,
      lastModified: lastUpdated,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${BASE}/accuracy`,
      lastModified: lastUpdated,
      changeFrequency: "weekly",
      priority: 0.7,
    },
    {
      url: `${BASE}/about`,
      lastModified: lastUpdated,
      changeFrequency: "monthly",
      priority: 0.4,
    },
  ];

  const raceEntries: MetadataRoute.Sitemap = Array.from(
    { length: totalRounds },
    (_, i) => i + 1
  ).map((round) => ({
    url: `${BASE}/race/${round}`,
    lastModified: lastUpdated,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  return [...staticEntries, ...raceEntries];
}
