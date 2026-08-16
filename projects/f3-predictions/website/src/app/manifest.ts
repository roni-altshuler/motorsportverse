import type { MetadataRoute } from "next";

/**
 * Web app manifest — emitted as /manifest.webmanifest at build time.
 *
 * The icon points at an asset that already exists in this site's tree rather
 * than a generated PNG set: a manifest referencing an icon that 404s is worse
 * than no manifest, because the browser caches the failure.
 *
 * `display: "browser"` on purpose. These are documents, not an app; an
 * installed standalone window would drop the URL bar from a site whose whole
 * job is publishing checkable numbers at stable addresses.
 */

// Required for static export.
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "RaceIQ F3 — Formula 3 predictions",
    short_name: "RaceIQ F3",
    description: "Sprint, feature-race and championship forecasts for FIA Formula 3, scored against real results.",
    start_url: ".",
    display: "browser",
    background_color: "#000000",
    theme_color: "#D9A441",
    icons: [{ src: "/icon.png", sizes: "any", type: "image/png" }],
  };
}
