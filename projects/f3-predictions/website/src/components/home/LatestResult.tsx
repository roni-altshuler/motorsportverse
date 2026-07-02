"use client";

import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import TeamColorBar from "@/components/ui/TeamColorBar";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { fadeUp } from "@/lib/motion";

export interface ResultRow {
  position: number;
  code: string;
  name?: string;
  team: string;
  teamColor: string;
  headshotUrl?: string | null;
}

interface LatestResultProps {
  /** Top-N feature-race finishers (already mapped + sorted). */
  feature: ResultRow[];
  /** Optional compact sprint podium sub-row. */
  sprint?: ResultRow[];
}

/**
 * "Latest Official Result" — the most recent completed round's FEATURE race
 * result, with an optional compact sprint podium sub-row. Ported from RaceIQ
 * F1's Latest Official Result table, adapted to F3's data (no times/grid). Fed
 * plain rows as props (never the fs loader). Reveal is animate-on-mount with a
 * reduced-motion fallback so content is never permanently invisible.
 */
export default function LatestResult({ feature, sprint }: LatestResultProps) {
  const reduced = useReducedMotion();

  const renderPos = (position: number) => {
    if (position === 1)
      return <span className="text-[color:var(--accent-podium-1)]">P1</span>;
    if (position === 2)
      return <span className="text-[color:var(--accent-podium-2)]">P2</span>;
    if (position === 3)
      return <span className="text-[color:var(--accent-podium-3)]">P3</span>;
    return `P${position}`;
  };

  return (
    <motion.div
      variants={fadeUp}
      initial={reduced ? "visible" : "hidden"}
      animate="visible"
    >
      <div className="border border-[color:var(--hairline)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[color:var(--hairline)]">
              <th className="px-4 py-3 text-left eyebrow">Pos</th>
              <th className="px-2 py-3 text-left eyebrow">Driver</th>
              <th className="px-2 py-3 text-left eyebrow hidden sm:table-cell">Team</th>
              <th className="px-4 py-3 text-right eyebrow">Status</th>
            </tr>
          </thead>
          <tbody>
            {feature.map((row) => (
              <tr
                key={row.code}
                className="border-b border-[color:var(--hairline)] last:border-b-0 transition-colors hover:bg-[color:var(--surface-card)]"
                data-team={row.team}
              >
                <td className="px-4 py-3 font-mono font-tabular text-[color:var(--muted)] w-14">
                  {renderPos(row.position)}
                </td>
                <td className="px-2 py-3">
                  <span className="inline-flex items-center gap-3">
                    <DriverPortrait
                      driver={row.code}
                      driverFullName={row.name}
                      team={row.team}
                      teamColor={row.teamColor}
                      headshotUrl={row.headshotUrl}
                      size={32}
                    />
                    <TeamColorBar teamColor={row.teamColor} team={row.team} size="sm" />
                    <span className="title-sm">{row.name ?? row.code}</span>
                  </span>
                </td>
                <td className="px-2 py-3 body-sm text-[color:var(--muted)] hidden sm:table-cell">
                  {row.team}
                </td>
                <td className="px-4 py-3 text-right font-mono font-tabular text-[color:var(--muted)]">
                  {row.position === 1 ? "WINNER" : "FINISHED"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sprint && sprint.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 px-1">
          <span className="eyebrow text-[color:var(--muted)]">Sprint podium</span>
          {sprint.map((row) => (
            <span
              key={row.code}
              data-team={row.team}
              className="inline-flex items-center gap-2 body-sm"
            >
              <span className="font-mono font-tabular text-[color:var(--muted)]">
                {renderPos(row.position)}
              </span>
              <TeamColorBar teamColor={row.teamColor} team={row.team} size="sm" />
              <span className="title-sm">{row.name ?? row.code}</span>
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}
