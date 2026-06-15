import type { Metadata } from "next";

import { StandingsTabs } from "@/components/StandingsTabs";
import { getF2Data, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Standings — RaceIQ F2" };

export default function StandingsPage() {
  const data = getF2Data();
  const colors: Record<string, string> = {};
  for (const t of data.teamStandings) colors[t.team] = teamColor(t.team);

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">Championship standings</h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        After {data.completedRounds} of {data.totalRounds} rounds · {data.season} season.
      </p>
      <div className="mt-10">
        <StandingsTabs
          drivers={data.driverStandings}
          teams={data.teamStandings}
          teamColor={colors}
        />
      </div>
    </div>
  );
}
