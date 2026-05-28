/**
 * Team logo resolution.
 *
 * Maps a team name to the asset path under `public/team-logos/`. We
 * keep an explicit team-name → filename map here because the
 * checked-in assets use mixed extensions (svg / png / jpg / webp /
 * avif) and CamelCase filenames that wouldn't survive a generic
 * slug-derivation rule.
 *
 * Add or update a team logo by:
 *   1. Dropping the file into `public/team-logos/`
 *   2. Updating the entry below with the team name + filename
 *
 * The UI's `<TeamBadge>` calls `teamLogoUrl(team)` and falls back to a
 * tinted initials badge when the asset is missing — see its
 * `onError` handler. No code change is needed to add a logo once the
 * mapping is in place.
 */

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";

/**
 * Team name → checked-in asset filename. Filenames are case-sensitive
 * and must match exactly what's under `public/team-logos/`.
 */
const LOGO_BY_TEAM: Record<string, string> = {
  Mercedes: "MercedesBenzLogo.png",
  "Red Bull Racing": "RedBullLogo.webp",
  Ferrari: "FerrariLogo.avif",
  McLaren: "MclarenLogo.jpg",
  "Aston Martin": "AstonMartinLogo.png",
  Alpine: "AlpineLogo.svg",
  Williams: "WilliamsLogo.png",
  "Racing Bulls": "RacingBullLogo.png",
  Haas: "HaasLogo.jpg",
  Audi: "AudiLogo.png",
  Cadillac: "CadillacLogo.webp",
};

/**
 * Slug derivation kept around for two reasons:
 *   - Diagnostics ("what slug WOULD this team have used")
 *   - Backwards-compat for any callers that want a stable identifier
 *     unrelated to the asset filename
 */
export function teamSlug(team: string): string {
  return team
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Resolve a team name to its logo URL. Returns null if we have no
 * mapping; the consumer falls back to an initials badge.
 */
export function teamLogoUrl(team: string | null | undefined): string | null {
  if (!team) return null;
  const filename = LOGO_BY_TEAM[team];
  if (!filename) return null;
  return `${PREFIX}/team-logos/${filename}`;
}
