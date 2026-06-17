// Pure, fs-free team helpers — safe to import from client components.
//
// Team colours come from the data now (single source of truth in config.TEAMS,
// surfaced as `teamColor` on each standing). This map is only a fallback for
// older payloads or unknown teams. Kept out of `f2data.ts` because that module
// imports `node:fs` for build-time loading, which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  "AIX Racing": "#C0392B",
  "ART Grand Prix": "#5A5A5A",
  "Campos Racing": "#1F3A93",
  "DAMS Lucas Oil": "#0090D0",
  "Hitech TGR": "#D4123A",
  "Invicta Racing": "#8E44AD",
  "MP Motorsport": "#F47C20",
  "PREMA Racing": "#E2001A",
  "Rodin Motorsport": "#00A19A",
  TRIDENT: "#0050A0",
  "Van Amersfoort Racing": "#FF5A00",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#1E9BD7";
}
