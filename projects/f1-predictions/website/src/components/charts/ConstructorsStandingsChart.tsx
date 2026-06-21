"use client";

import type { ConstructorStanding } from "@/types";
import TeamBadge from "@/components/standings/TeamBadge";
import ProgressionChart from "@/components/charts/ProgressionChart";

interface Props {
  data: ConstructorStanding[];
  /** Completed rounds, e.g. [1,2,3,4,5]. */
  rounds: number[];
  /** Total rounds in the season (e.g. 22). Used to extend the x-axis + forecast. */
  totalRounds?: number;
}

export default function ConstructorsStandingsChart({ data, rounds, totalRounds = 22 }: Props) {
  if (!data.length || !rounds.length) return null;

  const series = data.map((c) => ({
    key: c.team,
    label: c.team,
    color: c.teamColor,
    pointsHistory: c.pointsHistory ?? [],
  }));

  const legend = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {data.map((c) => (
        <span key={c.team} className="inline-flex items-center gap-1.5">
          <TeamBadge team={c.team} teamColor={c.teamColor} size={18} />
          <span style={{ color: "var(--text)" }}>{c.team}</span>
        </span>
      ))}
    </div>
  );

  return (
    <ProgressionChart series={series} rounds={rounds} totalRounds={totalRounds} legend={legend} />
  );
}
