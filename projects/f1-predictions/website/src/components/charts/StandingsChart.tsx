"use client";

import type { DriverStanding } from "@/types";
import DriverPortrait from "@/components/standings/DriverPortrait";
import ProgressionChart from "@/components/charts/ProgressionChart";

interface Props {
  data: DriverStanding[];
  /** Completed rounds, e.g. [1,2,3,4,5]. */
  rounds: number[];
  /** Total rounds in the season (e.g. 22). Used to extend the x-axis + forecast. */
  totalRounds?: number;
}

export default function StandingsChart({ data, rounds, totalRounds = 22 }: Props) {
  if (!data.length || !rounds.length) return null;

  const series = data.map((d) => ({
    key: d.driver,
    label: d.driver,
    color: d.teamColor,
    pointsHistory: d.pointsHistory ?? [],
  }));

  const legend = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {data.map((d) => (
        <span key={d.driver} className="inline-flex items-center gap-1.5">
          <DriverPortrait
            driver={d.driver}
            driverFullName={d.driverFullName}
            team={d.team}
            teamColor={d.teamColor}
            headshotUrl={d.headshotUrl}
            size={18}
          />
          <span style={{ color: "var(--text)" }}>{d.driver}</span>
        </span>
      ))}
    </div>
  );

  return (
    <ProgressionChart series={series} rounds={rounds} totalRounds={totalRounds} legend={legend} />
  );
}
