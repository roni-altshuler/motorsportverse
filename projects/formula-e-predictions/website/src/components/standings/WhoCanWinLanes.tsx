"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { teamColor as teamColorFor } from "@/lib/teams";
import type { TitleOdds } from "@/types/fe";

interface WhoCanWinLanesProps {
  championship: TitleOdds[];
  remainingRounds: number;
}

/**
 * Driver title-race forecast lanes (port of the RaceIQ F1 WhoCanWinLanes).
 * Each lane shows the driver portrait + team, championship-win probability
 * (bar + %), current → projected points, and the projected range (P10–P90).
 * Sourced directly from FE's `championship[]` (TitleOdds). Drivers below the
 * visibility threshold are grouped at the bottom as "mathematically out".
 */
const PROBABILITY_VISIBLE_THRESHOLD = 0.001;

interface Lane {
  code: string;
  name: string;
  team: string;
  teamColor: string;
  pTitle: number;
  currentPoints: number;
  projMean: number;
  projP10: number;
  projP90: number;
  canStillWin: boolean;
}

export default function WhoCanWinLanes({ championship, remainingRounds }: WhoCanWinLanesProps) {
  const reduced = useReducedMotion();

  const rows = useMemo<Lane[]>(() => {
    return [...championship]
      .map((c) => ({
        code: c.code,
        name: c.name,
        team: c.team,
        teamColor: teamColorFor(c.team),
        pTitle: c.pTitle,
        currentPoints: c.currentPoints,
        projMean: c.projMean,
        projP10: c.projP10,
        projP90: c.projP90,
        canStillWin: c.canStillWin ?? c.pTitle > 0,
      }))
      .sort((a, b) => b.pTitle - a.pTitle || b.projMean - a.projMean);
  }, [championship]);

  if (rows.length === 0) {
    return (
      <div className="space-y-6">
        <h2 className="display-md mb-2">Title Race Forecast</h2>
        <div className="card p-8 text-center">
          <p className="eyebrow mb-2">Forecast not yet computed</p>
          <p className="body-sm text-[color:var(--text-muted)] max-w-md mx-auto">
            The championship outlook publishes once the first weekend completes.
          </p>
        </div>
      </div>
    );
  }

  const top = rows[0];
  const topProb = top.pTitle;
  // A driver is "in the fight" if mathematically alive, even at <0.1% odds.
  const contenders = rows.filter(
    (r) => r.canStillWin || r.pTitle >= PROBABILITY_VISIBLE_THRESHOLD,
  );
  const eliminated = rows.filter(
    (r) => !r.canStillWin && r.pTitle < PROBABILITY_VISIBLE_THRESHOLD,
  );

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h2 className="display-md mb-2">Title Race Forecast</h2>
          <p className="body-md text-[color:var(--text-muted)] max-w-2xl">
            Championship win probability across the{" "}
            <span className="font-mono text-[color:var(--text)]">{remainingRounds}</span>{" "}
            remaining round{remainingRounds === 1 ? "" : "s"}. Updated after the latest round.
          </p>
        </div>
      </div>

      <div className="card p-4 sm:p-6">
        <ol className="space-y-2 sm:space-y-3">
          {contenders.map((row) => (
            <ForecastRow key={row.code} row={row} topProb={topProb} reduced={reduced} />
          ))}
        </ol>

        {eliminated.length > 0 && (
          <details className="mt-6 group">
            <summary className="cursor-pointer eyebrow text-[color:var(--text-muted)] hover:text-[color:var(--text)] transition-colors">
              Mathematically out · {eliminated.length} driver
              {eliminated.length === 1 ? "" : "s"} (click to expand)
            </summary>
            <ol className="mt-3 space-y-2 opacity-60">
              {eliminated.map((row) => (
                <ForecastRow key={row.code} row={row} topProb={topProb} reduced={reduced} dimmed />
              ))}
            </ol>
          </details>
        )}
      </div>

      <p className="text-xs text-[color:var(--text-muted)]">
        Title odds are projected from each driver&apos;s current form across the remaining
        E-Prix, applying the Formula E points system and accounting for retirement risk.
      </p>
    </div>
  );
}

interface ForecastRowProps {
  row: Lane;
  topProb: number;
  reduced: boolean;
  dimmed?: boolean;
}

function ForecastRow({ row, topProb, reduced, dimmed }: ForecastRowProps) {
  const widthPct = topProb > 0 ? (row.pTitle / topProb) * 100 : 0;
  const probLabel =
    row.pTitle >= 0.001
      ? `${(row.pTitle * 100).toFixed(row.pTitle >= 0.1 ? 1 : 2)}%`
      : "<0.1%";

  return (
    <li
      data-team={row.team}
      className="flex items-center gap-3 sm:gap-4"
      style={{ opacity: dimmed ? 0.55 : 1 }}
    >
      <DriverPortrait
        driver={row.code}
        driverFullName={row.name}
        team={row.team}
        teamColor={row.teamColor}
        headshotUrl={null}
        size={36}
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between mb-1 gap-3">
          <span
            className="font-display font-bold tracking-[0.04em] uppercase text-sm truncate"
            style={{ color: "var(--text)" }}
          >
            {row.name}
            <span
              className="ml-2 font-sans font-normal normal-case text-[10px] tracking-normal"
              style={{ color: "var(--text-muted)" }}
            >
              {row.team}
            </span>
          </span>
          <span
            className="font-mono tabular-nums text-sm font-bold whitespace-nowrap"
            style={{
              color: dimmed
                ? "var(--text-muted)"
                : row.pTitle >= 0.5
                ? "var(--success)"
                : "var(--text)",
            }}
          >
            {probLabel}
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
              boxShadow: dimmed
                ? undefined
                : `0 0 8px color-mix(in srgb, ${row.teamColor} 60%, transparent)`,
            }}
            initial={reduced ? false : { width: 0 }}
            animate={{ width: `${widthPct}%` }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>

        <div className="flex items-center justify-between mt-1.5 text-[11px] font-mono tabular-nums">
          <span style={{ color: "var(--text-muted)" }}>
            <NumberTicker value={row.currentPoints} />{" "}
            <span className="uppercase tracking-[0.1em]">pts now</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            <span className="uppercase tracking-[0.1em]">proj.</span>{" "}
            <span className="text-[color:var(--text)] font-bold">{row.projMean.toFixed(0)}</span>
            <span className="text-[10px] ml-1">
              ({row.projP10.toFixed(0)}–{row.projP90.toFixed(0)})
            </span>
          </span>
        </div>
      </div>
    </li>
  );
}
