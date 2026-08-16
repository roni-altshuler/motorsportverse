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
    name: "Chrome Valley Racing — a simulated story league",
    short_name: "Chrome Valley Racing",
    description: "A fan-made, fully simulated racing story league. Not a prediction of anything real.",
    start_url: ".",
    display: "browser",
    background_color: "#000000",
    theme_color: "#E10600",
    icons: [{ src: "/brand/mark.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
