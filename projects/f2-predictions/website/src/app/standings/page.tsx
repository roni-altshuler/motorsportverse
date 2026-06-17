import type { Metadata } from "next";

import { StandingsTabs } from "@/components/StandingsTabs";
import { getF2Data, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Standings — RaceIQ F2" };

export default function StandingsPage() {
  const data = getF2Data();
  const colors: Record<string, string> = {};
  for (const t of data.teamStandings) colors[t.team] = teamColor(t.team);

  // "Who can still win" — drivers still mathematically alive for the title.
  const contenders = data.championship.filter((c) => c.canStillWin);
  const eliminated = data.championship.length - contenders.length;

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">Championship standings</h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        After {data.completedRounds} of {data.totalRounds} rounds · {data.season} season.
      </p>

      {contenders.length > 0 && (
        <section className="mt-8 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5">
          <p className="eyebrow mb-3">
            Still in the title fight · {contenders.length} of {data.championship.length}
            {eliminated > 0 ? ` · ${eliminated} mathematically out` : ""}
          </p>
          <div className="flex flex-wrap gap-2">
            {contenders.slice(0, 8).map((c) => (
              <span
                key={c.code}
                className="rounded-full border px-3 py-1 text-xs text-[var(--ink)]"
                style={{ borderColor: `color-mix(in srgb, ${teamColor(c.team)} 60%, transparent)` }}
              >
                {c.name} ·{" "}
                <span style={{ color: "var(--accent)" }}>{(c.pTitle * 100).toFixed(1)}%</span>
              </span>
            ))}
          </div>
        </section>
      )}

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
