"use client";

import { motion } from "framer-motion";

import { NumberTicker } from "@/components/magicui/number-ticker";
import TeamBadge from "@/components/standings/TeamBadge";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { teamColor as teamColorFor } from "@/lib/teams";
import type { TeamStanding } from "@/types/f2";

interface ConstructorsForecastLanesProps {
  teams: TeamStanding[];
  remainingRounds: number;
  completedRounds: number;
}

/**
 * Teams title-race lanes (port of the RaceIQ F1 ConstructorsForecastLanes).
 *
 * F2 ships NO constructor title-odds array, so "who can still win" is DERIVED
 * here from the points standings:
 *
 *   - Per-round ceiling = max feature (25) + max sprint (10) + a small bonus
 *     (~2 for pole / fastest-lap) ≈ 37 pts/round for a team's best driver, so
 *     we use that as the per-round max a team can claw back.
 *   - maxAttainable = currentPoints + remainingRounds × CEILING.
 *   - A team is mathematically alive (canStillWin) when maxAttainable ≥ the
 *     leader's current points.
 *   - Projected total = current-pace extrapolation
 *     (currentPoints + per-round average × remainingRounds), bounded by the
 *     ceiling — honest "current pace", not a model forecast.
 *
 * The lane bar shows share-of-leader points (not fabricated odds), since we have
 * no real constructor title probability.
 */
const PER_ROUND_CEILING = 25 + 10 + 2;

interface Lane {
  team: string;
  teamColor: string;
  currentPoints: number;
  projected: number;
  maxAttainable: number;
  canStillWin: boolean;
}

export default function ConstructorsForecastLanes({
  teams,
  remainingRounds,
  completedRounds,
}: ConstructorsForecastLanesProps) {
  const reduced = useReducedMotion();

  if (!teams || teams.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="eyebrow mb-2">Teams outlook not yet available</p>
        <p className="body-sm text-[color:var(--text-muted)] max-w-md mx-auto">
          The teams&apos; title outlook publishes after the first round completes.
        </p>
      </div>
    );
  }

  const leaderPoints = teams[0]?.points ?? 0;

  const rows: Lane[] = teams.map((t) => {
    const perRound = completedRounds > 0 ? t.points / completedRounds : 0;
    const ceiling = remainingRounds * PER_ROUND_CEILING;
    const maxAttainable = t.points + ceiling;
    const projected = Math.min(t.points + perRound * remainingRounds, maxAttainable);
    return {
      team: t.team,
      teamColor: t.teamColor || teamColorFor(t.team),
      currentPoints: t.points,
      projected,
      maxAttainable,
      canStillWin: maxAttainable >= leaderPoints,
    };
  });

  const contenders = rows.filter((r) => r.canStillWin);
  const eliminated = rows.filter((r) => !r.canStillWin);

  return (
    <div className="card p-4 sm:p-6">
      <ol className="space-y-2 sm:space-y-3">
        {contenders.map((row) => (
          <ConstructorRow key={row.team} row={row} leaderPoints={leaderPoints} reduced={reduced} />
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
                leaderPoints={leaderPoints}
                reduced={reduced}
                dimmed
              />
            ))}
          </ol>
        </details>
      )}

      <p className="mt-4 text-xs text-[color:var(--text-muted)]">
        &ldquo;Still in the fight&rdquo; is derived from the points standings: a team is shown as
        alive while its maximum attainable total over the remaining rounds still reaches the
        leader. Projected totals extrapolate each team&apos;s current pace.
      </p>
    </div>
  );
}

interface ConstructorRowProps {
  row: Lane;
  leaderPoints: number;
  reduced: boolean;
  dimmed?: boolean;
}

function ConstructorRow({ row, leaderPoints, reduced, dimmed }: ConstructorRowProps) {
  const widthPct = leaderPoints > 0 ? (row.currentPoints / leaderPoints) * 100 : 0;

  return (
    <li
      data-team={row.team}
      className="flex items-center gap-3 sm:gap-4"
      style={{ opacity: dimmed ? 0.55 : 1 }}
    >
      <TeamBadge team={row.team} teamColor={row.teamColor} size={56} variant="card" />

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
            style={{ color: dimmed ? "var(--text-muted)" : "var(--text)" }}
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
            <span className="text-[color:var(--text)] font-bold">{row.projected.toFixed(0)}</span>
            <span className="text-[10px] ml-1">max {row.maxAttainable.toFixed(0)}</span>
          </span>
        </div>
      </div>
    </li>
  );
}
