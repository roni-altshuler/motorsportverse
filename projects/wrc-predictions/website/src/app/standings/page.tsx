import type { Metadata } from "next";

import type { ProgressionSeries } from "@/components/charts/ProgressionChart";
import StandingsPage from "@/components/StandingsPage";
import { getWrcData, getPointsProgression, teamColor } from "@/lib/wrcData";

export const metadata: Metadata = { title: "Standings — RaceIQ WRC" };

const TOP_DRIVERS = 6;

export default function Page() {
  const data = getWrcData();
  const prog = getPointsProgression();

  // Crew projected end-of-season totals come straight from championship[].projMean.
  const projByCode: Record<string, number> = {};
  for (const c of data.championship) projByCode[c.code] = c.projMean;

  // Only crews have a points progression to project: driverStandings carry a real
  // per-round pointsHistory and championship[] carries projMean. WRC manufacturer
  // standings publish neither history nor projection, so we deliberately derive no
  // manufacturer series — the manufacturer tab is a plain points standings.
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

  return (
    <StandingsPage
      season={data.season}
      completedRounds={data.completedRounds}
      totalRounds={data.totalRounds}
      lastUpdatedRound={data.lastUpdatedRound ?? data.completedRounds}
      drivers={data.driverStandings}
      manufacturers={data.manufacturerStandings}
      championship={data.championship}
      seasonAccuracy={data.seasonAccuracy}
      rounds={prog.rounds}
      driverSeries={driverSeries}
    />
  );
}
