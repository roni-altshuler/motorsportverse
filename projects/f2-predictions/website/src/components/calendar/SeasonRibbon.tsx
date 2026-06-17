"use client";

import { motion } from "framer-motion";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { CalendarRound } from "@/types/f2";

interface SeasonRibbonProps {
  calendar: CalendarRound[];
}

/**
 * Sticky horizontal ribbon (port of the RaceIQ F1 SeasonRibbon): one dot per
 * round, coloured by status. Completed rounds are solid (F2 accent blue);
 * upcoming rounds are hollow. The next round pulses + glows. Each dot links to
 * the round's detail page. The pulse honours prefers-reduced-motion.
 */
export default function SeasonRibbon({ calendar }: SeasonRibbonProps) {
  const reduced = useReducedMotion();
  const completedRounds = calendar.filter((r) => r.completed).map((r) => r.round);
  const lastCompleted = completedRounds.length ? Math.max(...completedRounds) : 0;
  const nextRound =
    calendar.find((r) => r.round > lastCompleted)?.round ??
    calendar[calendar.length - 1]?.round;

  return (
    <div className="sticky top-16 z-20 mb-8 backdrop-blur-md bg-[color:color-mix(in_srgb,var(--bg)_85%,transparent)] border border-[color:var(--hairline)] rounded-[var(--radius-card)] px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <p className="eyebrow">Season Ribbon</p>
        <p className="text-[10px] font-mono text-[color:var(--muted)]">
          Round {nextRound} next
        </p>
      </div>
      <div className="relative overflow-x-auto">
        <div className="flex items-center gap-1 min-w-max px-1 pb-2">
          {calendar.map((race, i) => {
            const completed = race.completed;
            const isNext = race.round === nextRound;
            const fill = completed ? "var(--accent)" : "transparent";
            const border = completed ? "var(--accent)" : "var(--hairline-strong)";
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
                  className="block w-4 h-4 rounded-full transition-transform hover:scale-125 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[color:var(--accent)]"
                  style={{
                    background: fill,
                    border: `1.5px solid ${border}`,
                    boxShadow: isNext ? "0 0 12px var(--accent)" : undefined,
                  }}
                  aria-label={`Round ${race.round}: ${race.name}`}
                />
                {isNext && !reduced && (
                  <motion.span
                    aria-hidden
                    className="absolute -bottom-1 w-1.5 h-1.5 rounded-full bg-[color:var(--accent)]"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.8, repeat: Infinity }}
                  />
                )}
                <span className="text-[9px] font-mono text-[color:var(--muted)] mt-1.5">
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
