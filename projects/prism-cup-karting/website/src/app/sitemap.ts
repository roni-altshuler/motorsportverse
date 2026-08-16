import type { MetadataRoute } from "next";

/**
 * sitemap.ts — generates /sitemap.xml at build time (App Router convention,
 * statically exported). Override the site URL with NEXT_PUBLIC_SITE_URL.
 *
 * Routes are listed explicitly rather than discovered: a sitemap built by
 * walking the filesystem at build time also lists routes that exist but are
 * not meant to be indexed, and there is no test that would catch it.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://motorsportverse.org/projects/prism-cup-karting";

const BASE = SITE_URL.replace(/\/$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  return [
    { url: `${BASE}/`, lastModified, changeFrequency: "weekly", priority: 1.0 },
    { url: `${BASE}/cups`, lastModified, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/racers`, lastModified, changeFrequency: "monthly", priority: 0.6 },
    { url: `${BASE}/tracks`, lastModified, changeFrequency: "monthly", priority: 0.6 },
  ];
}
