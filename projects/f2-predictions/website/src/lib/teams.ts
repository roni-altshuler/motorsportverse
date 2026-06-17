// Pure, fs-free team helpers — safe to import from client components.
//
// Team colours come from the data now (single source of truth in config.TEAMS,
// surfaced as `teamColor` on each standing). This map is only a fallback for
// older payloads or unknown teams. Kept out of `f2data.ts` because that module
// imports `node:fs` for build-time loading, which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  "ART Grand Prix": "#3B3B3B",
  "Prema Racing": "#E2001A",
  "MP Motorsport": "#F47C20",
  DAMS: "#0090D0",
  "Campos Racing": "#1F3A93",
  "Invicta Racing": "#8E44AD",
  Hitech: "#101820",
  "Rodin Motorsport": "#00A19A",
  "Van Amersfoort Racing": "#FF5A00",
  Trident: "#0050A0",
  "AIX Racing": "#C0392B",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#1E9BD7";
}
