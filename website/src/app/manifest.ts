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
    name: "MotorsportVerse",
    short_name: "MotorsportVerse",
    description: "The MotorsportVerse ecosystem hub — a catalog of open motorsport prediction projects on one shared core.",
    start_url: ".",
    display: "browser",
    background_color: "#060910",
    theme_color: "#e7102f",
    icons: [{ src: "/brand/favicon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
