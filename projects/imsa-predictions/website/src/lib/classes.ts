// Class helpers — the fs-free heart of IMSA's multi-class UI. Safe to import from
// client components (no node:fs). Everything here operates on the `classes[]`
// metadata the export carries on imsa.json and every per-round file.

import type { ClassMeta } from "@/types/imsa";

/** Fallback tint if a class key is somehow missing from the metadata. */
export const CLASS_FALLBACK_COLOR = "#999999";

/**
 * Site-level class-pill colour overrides. The IMSA export ships GTP with its
 * real class colour (#E10600, IMSA red), which collides with the red site
 * accent and leaves the GTP pill hard to read against accent surfaces — so the
 * SITE (never the JSON) recolours only the GTP pill to a distinct teal. Every
 * other class keeps the export's own colour. This is the one place that decides
 * pill colour; it is applied to class metadata at the data-loading boundary.
 */
export const CLASS_PILL_OVERRIDE: Record<string, string> = {
  GTP: "#2DD4BF",
};

/** A class colour with any site-level pill override applied. */
export function pillColor(key: string, exportColor: string | undefined): string {
  return CLASS_PILL_OVERRIDE[key] ?? exportColor ?? CLASS_FALLBACK_COLOR;
}

/** Return class metadata with pill-colour overrides applied (JSON untouched). */
export function withPillColors<T extends { key: string; color: string }>(list: T[]): T[] {
  return list.map((c) => ({ ...c, color: pillColor(c.key, c.color) }));
}

/** Look up a class's colour by key from a metadata list (override-aware). */
export function classColor(classes: ClassMeta[] | undefined, key: string): string {
  return pillColor(key, classes?.find((c) => c.key === key)?.color);
}

/** Look up a class's display label by key (falls back to the key itself). */
export function classLabel(classes: ClassMeta[] | undefined, key: string): string {
  return classes?.find((c) => c.key === key)?.label ?? key;
}

/**
 * Readable text colour (near-black vs white) for text sitting ON a filled
 * swatch of `hex`. Uses relative luminance — light class tints (green, amber)
 * get near-black ink; dark team colours get white.
 */
export function readableInk(hex: string): string {
  const h = hex.replace("#", "");
  const full =
    h.length === 3
      ? h.split("").map((c) => c + c).join("")
      : h.padEnd(6, "0").slice(0, 6);
  const r = parseInt(full.slice(0, 2), 16) / 255;
  const g = parseInt(full.slice(2, 4), 16) / 255;
  const b = parseInt(full.slice(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return lum > 0.45 ? "#04140d" : "#ffffff";
}
