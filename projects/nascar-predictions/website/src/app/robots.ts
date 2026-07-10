import type { MetadataRoute } from "next";

/**
 * robots.ts — emits /robots.txt at build time. Ported from the RaceIQ F1
 * flagship. Permits all crawlers and points at the sitemap.
 */

// Required for static export — Next.js needs to know this route is static.
export const dynamic = "force-static";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ||
  "https://motorsportverse.org/projects/nascar-predictions";

const BASE = SITE_URL.replace(/\/$/, "");

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${BASE}/sitemap.xml`,
  };
}
