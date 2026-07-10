// Pure, fs-free team helpers — safe to import from client components.
//
// Team colours come from the data (single source of truth in config.TEAMS,
// surfaced as `teamColor` on each standing). This map is only a fallback for
// older payloads or unknown teams — the 2026 IndyCar paddock, matching the
// export. Kept out of `indycardata.ts` because that module imports `node:fs`
// for build-time loading, which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  "Chip Ganassi Racing": "#D31217",
  "Team Penske": "#FFD100",
  "Arrow McLaren": "#FF8000",
  "Andretti Global": "#0A66C2",
  "Meyer Shank Racing": "#E5398D",
  "Rahal Letterman Lanigan Racing": "#1D449B",
  ECR: "#8626EC",
  "A.J. Foyt Enterprises": "#B22222",
  "Dale Coyne Racing": "#5A5A5A",
  "Juncos Hollinger Racing": "#00A19C",
  "Dreyer & Reinbold Racing": "#777777",
  "Abel Motorsports": "#2E8B57",
  "HMD Motorsports": "#101820",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#E0433D";
}

// Engine-supplier accents — Chevrolet / Honda. The data's engineStandings
// carries the same values; this is the fs-free fallback for client components
// (engine chips, standings panel).
const ENGINE_COLORS: Record<string, string> = {
  Chevrolet: "#C6A96E",
  Honda: "#CC0000",
};

export function engineColor(engine: string | undefined | null): string {
  return (engine && ENGINE_COLORS[engine]) || "#999999";
}
