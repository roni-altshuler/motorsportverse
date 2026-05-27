/**
 * Team logo resolution.
 *
 * The convention mirrors driver headshots: drop a transparent SVG (or
 * PNG) at `public/team-logos/<slug>.svg` and the UI will pick it up
 * automatically.  When the file is missing, `<TeamBadge>` falls back to
 * the team's initials inside a coloured ring, so missing logos degrade
 * gracefully without throwing 404s in the user's face.
 *
 * Add a logo by writing a file like:
 *   public/team-logos/mercedes.svg
 *   public/team-logos/red-bull-racing.svg
 *   public/team-logos/scuderia-ferrari.svg
 *
 * Slugs are derived from the team name via `teamSlug()` below.
 */

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";

/**
 * Canonicalise a team name to a URL-safe slug used as the filename of
 * the team logo asset. Examples:
 *   "Mercedes"            → "mercedes"
 *   "Red Bull Racing"     → "red-bull-racing"
 *   "Scuderia Ferrari"    → "scuderia-ferrari"
 *   "Sauber"              → "sauber"
 *   "Haas F1 Team"        → "haas-f1-team"
 */
export function teamSlug(team: string): string {
  return team
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Return the canonical logo URL for a team.  Always returns a string —
 * the UI is expected to handle the 404 case via TeamBadge's initials
 * fallback (an `onError` handler).
 */
export function teamLogoUrl(team: string | null | undefined): string | null {
  if (!team) return null;
  return `${PREFIX}/team-logos/${teamSlug(team)}.svg`;
}
