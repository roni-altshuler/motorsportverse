import type { Metadata } from "next";

import type { ProgressionSeries } from "@/components/charts/ProgressionChart";
import StandingsPage from "@/components/StandingsPage";
import { getF2Data, getPointsProgression, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Standings — RaceIQ F2" };

const TOP_DRIVERS = 6;
const TOP_TEAMS = 5;

export default function Page() {
  const data = getF2Data();
  const prog = getPointsProgression();

  // Driver projected end-of-season totals come straight from championship[].projMean.
  const projByCode: Record<string, number> = {};
  for (const c of data.championship) projByCode[c.code] = c.projMean;

  // Team projected totals = sum of the team's drivers' projMean (the brief's
  // "derive team projection from drivers" approach).
  const projByTeam: Record<string, number> = {};
  for (const c of data.championship) {
    projByTeam[c.team] = (projByTeam[c.team] ?? 0) + c.projMean;
  }

  const driverSeries: ProgressionSeries[] = data.driverStandings
    .slice(0, TOP_DRIVERS)
    .map((d) => ({
      key: d.code,
      label: d.code,
      color: d.teamColor || teamColor(d.team),
      history: prog.byCode[d.code] ?? d.pointsHistory ?? [],
      projectedTotal: projByCode[d.code] ?? d.points,
    }))
    .filter((s) => s.history.length > 0);

  const teamSeries: ProgressionSeries[] = data.teamStandings
    .slice(0, TOP_TEAMS)
    .map((t) => ({
      key: abbreviateTeam(t.team),
      label: t.team,
      color: t.teamColor || teamColor(t.team),
      history: prog.byTeam[t.team] ?? t.pointsHistory ?? [],
      projectedTotal: projByTeam[t.team] ?? t.points,
    }))
    .filter((s) => s.history.length > 0);

  return (
    <StandingsPage
      season={data.season}
      completedRounds={data.completedRounds}
      totalRounds={data.totalRounds}
      lastUpdatedRound={data.lastUpdatedRound ?? data.completedRounds}
      drivers={data.driverStandings}
      teams={data.teamStandings}
      championship={data.championship}
      seasonAccuracy={data.seasonAccuracy}
      rounds={prog.rounds}
      driverSeries={driverSeries}
      teamSeries={teamSeries}
    />
  );
}

// Short tag for the chart's tooltip/legend (full team names are too long).
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
