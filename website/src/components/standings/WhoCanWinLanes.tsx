"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type {
  ChampionshipForecast,
  StandingsData,
  WdcForecastEntry,
} from "@/types";

interface WhoCanWinLanesProps {
  standings: StandingsData;
  forecast: ChampionshipForecast | null;
}

/**
/**
 * Title-race forecast row per driver, sorted by championship win
 * probability descending. Each row shows:
 *
 *   - Driver portrait + team
 *   - Championship-win probability (bar + percentage)
 *   - Current points → projected final points
 *   - Projected points range (low / high)
 *
 * Drivers below the visibility threshold are grouped at the bottom
 * as "mathematically out" — they cannot reach the title in any
 * projected outcome.
 */
const PROBABILITY_VISIBLE_THRESHOLD = 0.001;

export default function WhoCanWinLanes({
  standings,
  forecast,
}: WhoCanWinLanesProps) {
  const reduced = useReducedMotion();

  // When the simulator output is missing (pre-deploy or first run),
  // fall back to the static feasibility list so the UI still renders
  // something useful.
  const rows = useMemo<WdcForecastEntry[]>(() => {
    if (forecast?.wdcForecast?.length) {
      return forecast.wdcForecast;
    }
    return (standings.wdcPossibility ?? []).map((w) => ({
      driver: w.driver,
      driverFullName: w.driverFullName,
      team: w.team,
      teamColor: w.teamColor,
      currentPoints: w.currentPoints,
      championshipWinProbability: w.canStillWin ? 0.001 : 0,
      expectedFinalPoints: w.maxPossiblePoints,
      expectedFinalPosition: 0,
      p5thPercentilePoints: w.currentPoints,
      p95thPercentilePoints: w.maxPossiblePoints,
    }));
  }, [forecast, standings.wdcPossibility]);

  if (rows.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="display-md mb-2">Title Race Forecast</h2>
        </div>
        <div className="card p-8 text-center">
          <p className="eyebrow mb-2">Forecast not yet computed</p>
          <p className="body-sm text-[color:var(--text-muted)] max-w-md mx-auto">
            The championship simulator publishes once the first race weekend
            completes. Check back after Round{" "}
            {(standings.lastUpdatedRound ?? 0) + 1}.
          </p>
        </div>
      </div>
    );
  }

  const top = rows[0];
  const topProb = top.championshipWinProbability;
  const contenders = rows.filter(
    (r) => r.championshipWinProbability >= PROBABILITY_VISIBLE_THRESHOLD,
  );
  const eliminated = rows.filter(
    (r) => r.championshipWinProbability < PROBABILITY_VISIBLE_THRESHOLD,
  );

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h2 className="display-md mb-2">Title Race Forecast</h2>
          <p className="body-md text-[color:var(--text-muted)] max-w-2xl">
            Championship win probability across the{" "}
            <span className="font-mono text-[color:var(--text)]">
              {forecast?.remainingRounds ?? 0}
            </span>{" "}
            remaining round
            {forecast?.remainingRounds === 1 ? "" : "s"}. Updated after the
            latest Grand Prix.
          </p>
        </div>
      </div>

      <div className="card p-4 sm:p-6">
        <ol className="space-y-2 sm:space-y-3">
          {contenders.map((row) => (
            <ForecastRow
              key={row.driver}
              row={row}
              topProb={topProb}
              reduced={reduced}
            />
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
                <ForecastRow
                  key={row.driver}
                  row={row}
                  topProb={topProb}
                  reduced={reduced}
                  dimmed
                />
              ))}
            </ol>
          </details>
        )}
      </div>

      <p className="text-xs text-[color:var(--text-muted)]">
        Title odds are projected from the model&apos;s current form-card
        across the remaining race weekends, applying the official points
        system (including sprint and fastest-lap bonuses) and accounting
        for retirement risk.
      </p>
    </div>
  );
}

interface ForecastRowProps {
  row: WdcForecastEntry;
  topProb: number;
  reduced: boolean;
  dimmed?: boolean;
}

function ForecastRow({ row, topProb, reduced, dimmed }: ForecastRowProps) {
  // Bar width: P(WDC) normalised to the leader's probability so the bar
  // visually compares title chances head-to-head.  Eliminated rows have
  // 0% bar width.
  const widthPct = topProb > 0 ? (row.championshipWinProbability / topProb) * 100 : 0;
  const probLabel = row.championshipWinProbability >= 0.001
    ? `${(row.championshipWinProbability * 100).toFixed(row.championshipWinProbability >= 0.1 ? 1 : 2)}%`
    : "<0.1%";

  return (
    <li
      data-team={row.team}
      className="flex items-center gap-3 sm:gap-4"
      style={{ opacity: dimmed ? 0.55 : 1 }}
    >
      <DriverPortrait
        driver={row.driver}
        driverFullName={row.driverFullName}
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
            {row.driver}
            <span
              className="ml-2 font-sans font-normal normal-case text-[10px] tracking-normal"
              style={{ color: "var(--text-muted)" }}
            >
              {row.team}
            </span>
          </span>
          <span
            className="font-mono font-tabular text-sm font-bold whitespace-nowrap"
            style={{
              color: dimmed
                ? "var(--text-muted)"
                : row.championshipWinProbability >= 0.5
                ? "var(--success)"
                : "var(--text)",
            }}
          >
            {probLabel}
          </span>
        </div>

        {/* Probability bar */}
        <div
          className="relative h-2 rounded-full overflow-hidden"
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border)",
          }}
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

        {/* Points info */}
        <div className="flex items-center justify-between mt-1.5 text-[11px] font-mono font-tabular">
          <span style={{ color: "var(--text-muted)" }}>
            <NumberTicker value={row.currentPoints} />{" "}
            <span className="uppercase tracking-[0.1em]">pts now</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            <span className="uppercase tracking-[0.1em]">proj.</span>{" "}
            <span className="text-[color:var(--text)] font-bold">
              {row.expectedFinalPoints.toFixed(0)}
            </span>
            <span className="text-[10px] ml-1">
              ({row.p5thPercentilePoints.toFixed(0)}–{row.p95thPercentilePoints.toFixed(0)})
            </span>
          </span>
        </div>
      </div>
    </li>
  );
}
