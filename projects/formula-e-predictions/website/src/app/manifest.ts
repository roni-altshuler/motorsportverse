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
    name: "RaceIQ Formula E — Formula E predictions",
    short_name: "RaceIQ Formula E",
    description: "Race and championship forecasts for the ABB FIA Formula E World Championship.",
    start_url: ".",
    display: "browser",
    background_color: "#000000",
    theme_color: "#1E1AF0",
    icons: [{ src: "/icon.png", sizes: "any", type: "image/png" }],
  };
}
