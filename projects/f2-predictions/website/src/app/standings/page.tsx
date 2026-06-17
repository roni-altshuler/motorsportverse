import type { Metadata } from "next";

import type { ProgressionSeries } from "@/components/charts/ProgressionChart";
import { StandingsProgression } from "@/components/charts/StandingsProgression";
import { StandingsTabs } from "@/components/StandingsTabs";
import { getF2Data, getPointsProgression, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Standings — RaceIQ F2" };

const TOP_DRIVERS = 6;
const TOP_TEAMS = 5;

export default function StandingsPage() {
  const data = getF2Data();
  const colors: Record<string, string> = {};
  for (const t of data.teamStandings) colors[t.team] = teamColor(t.team);

  // "Who can still win" — drivers still mathematically alive for the title.
  const contenders = data.championship.filter((c) => c.canStillWin);
  const eliminated = data.championship.length - contenders.length;

  // Build projection series from the reconstructed points history + per-entity
  // projected totals (driver projMean; team = Σ of its drivers' projMean).
  const prog = getPointsProgression();
  const projByCode: Record<string, number> = {};
  for (const c of data.championship) projByCode[c.code] = c.projMean;

  const driverSeries: ProgressionSeries[] = data.driverStandings
    .slice(0, TOP_DRIVERS)
    .map((d) => ({
      key: d.code,
      label: d.name,
      color: teamColor(d.team),
      history: prog.byCode[d.code] ?? [],
      projectedTotal: projByCode[d.code] ?? d.points,
    }))
    .filter((s) => s.history.length > 0);

  const projByTeam: Record<string, number> = {};
  for (const c of data.championship) {
    projByTeam[c.team] = (projByTeam[c.team] ?? 0) + c.projMean;
  }
  const teamSeries: ProgressionSeries[] = data.teamStandings
    .slice(0, TOP_TEAMS)
    .map((t) => ({
      key: abbreviateTeam(t.team),
      label: t.team,
      color: teamColor(t.team),
      history: prog.byTeam[t.team] ?? [],
      projectedTotal: projByTeam[t.team] ?? t.points,
    }))
    .filter((s) => s.history.length > 0);

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <p className="eyebrow mb-3">Formula 2 · {data.season}</p>
      <h1 className="font-display text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        Championship standings
      </h1>
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
                <span className="font-tabular" style={{ color: "var(--accent)" }}>
                  {(c.pTitle * 100).toFixed(1)}%
                </span>
              </span>
            ))}
          </div>
        </section>
      )}

      {driverSeries.length > 0 && (
        <StandingsProgression
          driverSeries={driverSeries}
          teamSeries={teamSeries}
          rounds={prog.rounds}
          totalRounds={data.totalRounds}
        />
      )}

      <div className="mt-12">
        <StandingsTabs
          drivers={data.driverStandings}
          teams={data.teamStandings}
          teamColor={colors}
        />
      </div>
    </div>
  );
}

// Short tag for the chart's end-of-line label (team names are too long).
function abbreviateTeam(team: string): string {
  const map: Record<string, string> = {
    "Prema Racing": "PRE",
    Trident: "TRI",
    DAMS: "DAM",
    "MP Motorsport": "MP",
    "Campos Racing": "CAM",
    "ART Grand Prix": "ART",
    "Invicta Racing": "INV",
    "Van Amersfoort Racing": "VAR",
    Hitech: "HIT",
    "Rodin Motorsport": "ROD",
    "AIX Racing": "AIX",
  };
  return map[team] ?? team.slice(0, 3).toUpperCase();
}
