// Pure, fs-free team helpers — safe to import from client components.
//
// Team colours come from the data (single source of truth in config.TEAMS,
// surfaced as `teamColor` on each standing). This map is only a fallback for
// older payloads or unknown teams — the 2026 NASCAR Cup garage, matching the
// export. Kept out of `nascardata.ts` because that module imports `node:fs`
// for build-time loading, which must never reach the client.

const TEAM_COLORS: Record<string, string> = {
  "23XI Racing": "#5B2D8E",
  "Beard Motorsports": "#FFD659",
  "Front Row Motorsports": "#B7312C",
  "Garage 66": "#FFD659",
  "HYAK Motorsports": "#0072CE",
  "Haas Factory Team": "#4B4F54",
  "Hendrick Motorsports": "#D6001C",
  "JR Motorsports": "#FFD659",
  "Joe Gibbs Racing": "#0A6B3B",
  "Kaulig Racing": "#00843D",
  "Legacy Motor Club": "#8A8D8F",
  "Live Fast Motorsports": "#FFD659",
  "NY Racing Team": "#FFD659",
  "RFK Racing": "#1B4499",
  "Richard Childress Racing": "#F5B300",
  "Rick Ware Racing": "#6C6F70",
  "Spire Motorsports": "#00B2A9",
  "Team Penske": "#FFD100",
  "Trackhouse Racing": "#E4002B",
  "Wood Brothers Racing": "#C8102E",
};

export function teamColor(team: string): string {
  return TEAM_COLORS[team] || "#E9BC2F";
}

// Manufacturer accents — Chevrolet / Ford / Toyota. The data's
// manufacturerStandings carries the same values; this is the fs-free fallback
// for client components (manufacturer chips, standings panel).
const MAKE_COLORS: Record<string, string> = {
  Chevrolet: "#C6A96E",
  Toyota: "#EB0A1E",
  Ford: "#003478",
};

export function makeColor(make: string | undefined | null): string {
  return (make && MAKE_COLORS[make]) || "#999999";
}
