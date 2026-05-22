"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import TeamColorBar from "@/components/ui/TeamColorBar";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { podiumReveal } from "@/lib/motion";

interface PodiumEntry {
  driver: string;
  driverFullName?: string;
  team: string;
  teamColor: string;
  winProbability?: number;
  predictedTime?: number;
  gap?: string;
}

interface PodiumStageProps {
  entries: PodiumEntry[];
  /** Delay (ms) before the stagger starts.  Used by HomePage to sync
   * the reveal with the lights-out sequence. */
  startDelay?: number;
  /** Whether to skip the reveal stagger (e.g. when an event already
   * fired upstream). */
  immediate?: boolean;
}

const POSITION_LABELS = ["P1", "P2", "P3"];

export default function PodiumStage({ entries, startDelay = 0, immediate = false }: PodiumStageProps) {
  const reduced = useReducedMotion();
  const slots = entries.slice(0, 3);
  while (slots.length < 3) slots.push({ driver: "—", team: "—", teamColor: "var(--text-muted)" });

  // Re-order so P1 sits visually in the center on desktop: P2 (left), P1 (center, taller), P3 (right).
  const ordered: { entry: PodiumEntry; rank: 0 | 1 | 2; order: number }[] = [
    { entry: slots[1], rank: 1, order: 0 },
    { entry: slots[0], rank: 0, order: 1 },
    { entry: slots[2], rank: 2, order: 2 },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-5 items-end">
      {ordered.map(({ entry, rank, order }, idx) => {
        const isLeader = rank === 0;
        return (
          <motion.div
            key={`${entry.driver}-${rank}`}
            custom={immediate || reduced ? 0 : idx}
            initial={reduced ? "visible" : "hidden"}
            animate="visible"
            variants={podiumReveal}
            transition={{ delay: startDelay / 1000 }}
            style={{ order } as React.CSSProperties}
            className={isLeader ? "sm:-translate-y-2" : ""}
          >
            <Card
              surface="paddock"
              team={entry.team}
              teamColor={entry.teamColor}
              className={`p-5 sm:p-6 relative overflow-hidden ${isLeader ? "sm:py-8" : ""}`}
              style={isLeader ? { boxShadow: "var(--glow-podium)" } : undefined}
            >
              <div className="flex items-center gap-3 mb-4">
                <span
                  className={`font-mono font-tabular text-3xl ${isLeader ? "sm:text-4xl" : ""} font-black tracking-tight ${
                    isLeader ? "text-[color:var(--hud-champagne)]" : "text-[color:var(--text-muted)]"
                  }`}
                  aria-hidden
                >
                  {POSITION_LABELS[rank]}
                </span>
                <TeamColorBar
                  teamColor={entry.teamColor}
                  team={entry.team}
                  variant="gradient"
                  size={isLeader ? "lg" : "md"}
                  animate="draw"
                />
              </div>
              <div className={`font-black tracking-tight mb-1 ${isLeader ? "text-3xl sm:text-4xl" : "text-2xl sm:text-3xl"}`}>
                {entry.driver}
              </div>
              <div className="text-sm text-[color:var(--text-muted)] mb-5">{entry.driverFullName ?? entry.team}</div>
              <div className="hud-kicker mb-1">Win probability</div>
              {entry.winProbability != null && entry.winProbability > 0 ? (
                <AnimatedNumber
                  value={entry.winProbability}
                  decimals={1}
                  suffix="%"
                  variant={isLeader ? "huge" : "default"}
                  className="text-[color:var(--accent-live)]"
                />
              ) : (
                <span className="font-mono font-tabular text-3xl font-black text-[color:var(--text-muted)]">—</span>
              )}
              {entry.gap && (
                <p className="mt-3 text-xs font-mono text-[color:var(--text-muted)]">
                  {entry.gap === "LEADER" ? "Projected leader" : `+${entry.gap}`}
                </p>
              )}
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
