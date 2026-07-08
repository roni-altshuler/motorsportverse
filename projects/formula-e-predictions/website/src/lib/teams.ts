// Pure, fs-free team helpers — safe to import from client components.
//
// Team colours come from the data (single source of truth in config.TEAMS,
// surfaced as `teamColor` on each standing). This map is only a fallback for
// older payloads or unknown teams — the 2025-26 Formula E grid, matching the
// export. Kept out of `fedata.ts` because that module imports `node:fs` for
// build-time loading, which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  "Jaguar TCS Racing": "#C9A227",
  Porsche: "#D5001C",
  Andretti: "#F26522",
  "Mahindra Racing": "#E31837",
  "Envision Racing": "#00C900",
  Nissan: "#E4287C",
  "Citro\u00ebn Racing": "#EB002A",
  "CUPRA KIRO": "#2AA8A0",
  "DS Penske": "#CBA65F",
  "Lola Yamaha ABT": "#0033A0",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#4B48FF";
}
