"use client";

import { motion } from "framer-motion";

import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamBadge from "@/components/standings/TeamBadge";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ChampionshipForecast, WccForecastEntry } from "@/types";

interface ConstructorsForecastLanesProps {
  forecast: ChampionshipForecast | null;
}

const PROBABILITY_VISIBLE_THRESHOLD = 0.001;

export default function ConstructorsForecastLanes({
  forecast,
}: ConstructorsForecastLanesProps) {
  const reduced = useReducedMotion();
  const rows = forecast?.wccForecast ?? [];

  if (rows.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="eyebrow mb-2">Constructors outlook not yet available</p>
        <p className="body-sm text-[color:var(--text-muted)] max-w-md mx-auto">
          The constructors&apos; title outlook publishes after the first race
          weekend completes.
        </p>
      </div>
    );
  }

  const topProb = rows[0]?.championshipWinProbability ?? 0;
  const contenders = rows.filter(
    (r) => r.championshipWinProbability >= PROBABILITY_VISIBLE_THRESHOLD,
  );
  const eliminated = rows.filter(
    (r) => r.championshipWinProbability < PROBABILITY_VISIBLE_THRESHOLD,
  );

  return (
    <div className="card p-4 sm:p-6">
      <ol className="space-y-2 sm:space-y-3">
        {contenders.map((row) => (
          <ConstructorRow
            key={row.team}
            row={row}
            topProb={topProb}
            reduced={reduced}
          />
        ))}
      </ol>

      {eliminated.length > 0 && (
        <details className="mt-6 group">
          <summary className="cursor-pointer eyebrow text-[color:var(--text-muted)] hover:text-[color:var(--text)] transition-colors">
            Mathematically out · {eliminated.length} team
            {eliminated.length === 1 ? "" : "s"} (click to expand)
          </summary>
          <ol className="mt-3 space-y-2 opacity-60">
            {eliminated.map((row) => (
              <ConstructorRow
                key={row.team}
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
  );
}

interface ConstructorRowProps {
  row: WccForecastEntry;
  topProb: number;
  reduced: boolean;
  dimmed?: boolean;
}

function ConstructorRow({ row, topProb, reduced, dimmed }: ConstructorRowProps) {
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
      <TeamBadge
        team={row.team}
        teamColor={row.teamColor}
        size={56}
        variant="card"
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between mb-1 gap-3">
          <span
            className="font-display font-bold tracking-[0.04em] uppercase text-sm truncate"
            style={{ color: "var(--text)" }}
          >
            {row.team}
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
