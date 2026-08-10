/**
 * surface.ts — WRC's signature variable.
 *
 * Every round is run on gravel, tarmac or snow, and that surface is the single
 * biggest driver of who is fast. The colour for each surface comes from the
 * data (`surfaceColor` on the calendar / round / probabilities payloads); this
 * module only supplies a canonical fallback colour and a display label, so a
 * chip renders consistently everywhere. Pure + fs-free — safe on the client.
 */

export type Surface = "gravel" | "tarmac" | "snow";

/** Canonical fallback colours (also emitted in the data — prefer the data). */
export const SURFACE_COLORS: Record<string, string> = {
  gravel: "#B8722C",
  tarmac: "#5B6670",
  snow: "#7FB2D9",
};

/** Title-cased display label for a surface. */
export function surfaceLabel(surface: string | null | undefined): string {
  if (!surface) return "—";
  return surface.charAt(0).toUpperCase() + surface.slice(1).toLowerCase();
}

/** Resolve a surface's chip colour, preferring an explicit value from the data. */
export function surfaceColor(
  surface: string | null | undefined,
  explicit?: string | null,
): string {
  if (explicit) return explicit;
  if (!surface) return "#5B6670";
  return SURFACE_COLORS[surface.toLowerCase()] ?? "#5B6670";
}
