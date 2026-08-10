// Pure, fs-free manufacturer helpers — safe to import from client components.
//
// Manufacturer colours come from the data now (single source of truth in the
// pipeline, surfaced as `teamColor` on each standing). This map is only a
// fallback for older payloads or unknown manufacturers. Kept out of
// `wrcData.ts` because that module imports `node:fs` for build-time loading,
// which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  Toyota: "#EB0A1E",
  Hyundai: "#0B2C5F",
  Ford: "#1B3E8C",
  Skoda: "#4BA82E",
  Citroen: "#C8102E",
  Lancia: "#003F87",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#0F62FE";
}
