"use client";

import { motion } from "framer-motion";

import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamBadge from "@/components/standings/TeamBadge";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { teamColor as teamColorFor } from "@/lib/teams";
import type { ManufacturerStanding } from "@/types/wrc";

interface ManufacturerPointsLanesProps {
  teams: ManufacturerStanding[];
}

/**
 * Manufacturer points-share lanes (repurposed from the RaceIQ F1
 * ConstructorsForecastLanes).
 *
 * WRC publishes ONLY current manufacturer points — no per-manufacturer
 * projection, history, wins or podiums — so there is nothing to forecast here.
 * This panel therefore shows each manufacturer's current points as a share of
 * the leader's total. Nothing is fabricated: the bar width is the honest
 * points-share, straight from the published standings.
 */
interface Lane {
  team: string;
  teamColor: string;
  points: number;
}

export default function ConstructorsForecastLanes({
  teams,
}: ManufacturerPointsLanesProps) {
  const reduced = useReducedMotion();

  if (!teams || teams.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="eyebrow mb-2">Manufacturer standings not yet available</p>
        <p className="body-sm text-[color:var(--text-muted)] max-w-md mx-auto">
          The manufacturers&apos; championship publishes after the first round completes.
        </p>
      </div>
    );
  }

  const leaderPoints = teams[0]?.points ?? 0;

  const rows: Lane[] = teams.map((t) => ({
    team: t.team,
    teamColor: t.teamColor || teamColorFor(t.team),
    points: t.points,
  }));

  return (
    <div className="card p-4 sm:p-6">
      <ol className="space-y-2 sm:space-y-3">
        {rows.map((row) => (
          <ManufacturerRow
            key={row.team}
            row={row}
            leaderPoints={leaderPoints}
            reduced={reduced}
          />
        ))}
      </ol>

      <p className="mt-4 text-xs text-[color:var(--text-muted)]">
        Each bar is the manufacturer&apos;s current championship points as a share of the
        leader&apos;s total.
      </p>
    </div>
  );
}

interface ManufacturerRowProps {
  row: Lane;
  leaderPoints: number;
  reduced: boolean;
}

function ManufacturerRow({ row, leaderPoints, reduced }: ManufacturerRowProps) {
  const widthPct = leaderPoints > 0 ? (row.points / leaderPoints) * 100 : 0;

  return (
    <li data-team={row.team} className="flex items-center gap-3 sm:gap-4">
      <TeamBadge team={row.team} teamColor={row.teamColor} size={44} />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between mb-1 gap-3">
          <span
            className="font-display font-bold tracking-[0.04em] uppercase text-sm truncate"
            style={{ color: "var(--text)" }}
          >
            {row.team}
          </span>
          <span
            className="font-mono tabular-nums text-sm font-bold whitespace-nowrap"
            style={{ color: "var(--text)" }}
          >
            {Math.round(widthPct)}% of leader
          </span>
        </div>

        <div
          className="relative h-2 rounded-full overflow-hidden"
          style={{ background: "var(--surface-card)", border: "1px solid var(--border)" }}
        >
          <motion.div
            className="absolute inset-y-0 left-0"
            style={{
              background: row.teamColor,
              width: `${widthPct}%`,
              boxShadow: `0 0 8px color-mix(in srgb, ${row.teamColor} 60%, transparent)`,
            }}
            initial={reduced ? false : { width: 0 }}
            animate={{ width: `${widthPct}%` }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>

        <div className="flex items-center justify-between mt-1.5 text-[11px] font-mono tabular-nums">
          <span style={{ color: "var(--text-muted)" }}>
            <NumberTicker value={row.points} />{" "}
            <span className="uppercase tracking-[0.1em]">pts</span>
          </span>
        </div>
      </div>
    </li>
  );
}
