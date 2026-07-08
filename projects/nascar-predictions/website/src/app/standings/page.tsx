import type { Metadata } from "next";

import type { ProgressionSeries } from "@/components/charts/ProgressionChart";
import StandingsPage from "@/components/StandingsPage";
import {
  getNascarData,
  getPlayoffProjection,
  getPointsProgression,
  playoffGatePassed,
  teamColor,
} from "@/lib/nascardata";

export const metadata: Metadata = { title: "Standings — RaceIQ NASCAR" };

const TOP_DRIVERS = 6;
const TOP_TEAMS = 5;

export default function Page() {
  const data = getNascarData();
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

  // The Chase panel ships ONLY when the playoff simulator passed its
  // historical honesty gate (historical_backtest/playoffs.json → gate.pass).
  const playoffProjection = playoffGatePassed() ? getPlayoffProjection() : null;

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
      manufacturers={data.manufacturerStandings ?? []}
      playoffProjection={playoffProjection}
    />
  );
}

// Short tag for the chart's tooltip/legend (full team names are too long).
function abbreviateTeam(team: string): string {
  const map: Record<string, string> = {
    "Hendrick Motorsports": "HMS",
    "Joe Gibbs Racing": "JGR",
    "Team Penske": "PEN",
    "23XI Racing": "23XI",
    "Trackhouse Racing": "TRK",
    "RFK Racing": "RFK",
    "Richard Childress Racing": "RCR",
    "Spire Motorsports": "SPI",
    "Front Row Motorsports": "FRM",
    "Wood Brothers Racing": "WBR",
    "Legacy Motor Club": "LMC",
    "Haas Factory Team": "HFT",
    "Kaulig Racing": "KAU",
    "HYAK Motorsports": "HYK",
    "Rick Ware Racing": "RWR",
  };
  return map[team] ?? team.slice(0, 3).toUpperCase();
}
