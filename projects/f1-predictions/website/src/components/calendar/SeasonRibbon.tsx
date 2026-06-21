"use client";

import { motion } from "framer-motion";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { RaceCalendarEntry } from "@/types";

interface SeasonRibbonProps {
  calendar: RaceCalendarEntry[];
  completedRounds: number[];
  actualRounds: Set<number>;
}

/**
 * Sticky horizontal ribbon: one dot per round, coloured by status.
 * Past rounds: solid; upcoming: hollow.  A "now" indicator pulses
 * between the last completed round and the next upcoming round.
 */
export default function SeasonRibbon({ calendar, completedRounds, actualRounds }: SeasonRibbonProps) {
  const reduced = useReducedMotion();
  const lastCompleted = Math.max(0, ...completedRounds);
  const nextRound = calendar.find((r) => r.round > lastCompleted)?.round ?? calendar[calendar.length - 1]?.round;

  return (
    <div className="sticky top-16 z-20 mb-8 backdrop-blur-md bg-[color:color-mix(in_srgb,var(--bg)_85%,transparent)] border border-[color:var(--border)] rounded-xl px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <p className="hud-kicker">Season Ribbon</p>
        <p className="text-[10px] font-mono text-[color:var(--text-muted)]">
          Round {nextRound} next
        </p>
      </div>
      <div className="relative overflow-x-auto">
        <div className="flex items-center gap-1 min-w-max px-1 pb-2">
          {calendar.map((race, i) => {
            const completed = completedRounds.includes(race.round);
            const hasActual = actualRounds.has(race.round);
            const isNext = race.round === nextRound;
            const fill = hasActual
              ? "var(--accent-positive)"
              : completed
              ? "var(--accent-live)"
              : "transparent";
            const border = hasActual
              ? "var(--accent-positive)"
              : completed
              ? "var(--accent-live)"
              : "var(--border-strong)";
            return (
              <motion.div
                key={race.round}
                initial={reduced ? false : { opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: reduced ? 0 : i * 0.025, duration: 0.25 }}
                className="relative flex flex-col items-center"
                title={`R${race.round}: ${race.name}`}
              >
                <a
                  href={`/race/${race.round}`}
                  className="block w-4 h-4 rounded-full transition-transform hover:scale-125 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[color:var(--accent-live)]"
                  style={{
                    background: fill,
                    border: `1.5px solid ${border}`,
                    boxShadow: isNext ? "0 0 12px var(--accent-live)" : undefined,
                  }}
                  aria-label={`Round ${race.round}: ${race.name}`}
                />
                {isNext && !reduced && (
                  <motion.span
                    aria-hidden
                    className="absolute -bottom-1 w-1.5 h-1.5 rounded-full bg-[color:var(--accent-live)]"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.8, repeat: Infinity }}
                  />
                )}
                <span className="text-[9px] font-mono text-[color:var(--text-muted)] mt-1.5">
                  {race.round}
                </span>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
