// Pure, fs-free manufacturer helpers — safe to import from client components.
//
// Manufacturer colours come from the data now (single source of truth in
// config.TEAMS, surfaced as `teamColor` on each standing). This map is only a
// fallback for older payloads or unknown manufacturers. Kept out of
// `motogpData.ts` because that module imports `node:fs` for build-time loading,
// which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  Aprilia: "#22A6A0",
  Ducati: "#C8102E",
  KTM: "#FF6900",
  Yamaha: "#0A2472",
  Honda: "#1C4E9C",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#CC0000";
}
