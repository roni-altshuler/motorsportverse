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
  startDelay?: number;
  immediate?: boolean;
}

const POSITION_LABELS = ["P1", "P2", "P3"];

export default function PodiumStage({ entries, startDelay = 0, immediate = false }: PodiumStageProps) {
  const reduced = useReducedMotion();
  const slots = entries.slice(0, 3);
  while (slots.length < 3) slots.push({ driver: "—", team: "—", teamColor: "var(--muted)" });

  const ordered: { entry: PodiumEntry; rank: 0 | 1 | 2; order: number }[] = [
    { entry: slots[1], rank: 1, order: 0 },
    { entry: slots[0], rank: 0, order: 1 },
    { entry: slots[2], rank: 2, order: 2 },
  ];

  const positionColor = (rank: 0 | 1 | 2) =>
    rank === 0
      ? "text-[color:var(--accent-podium-1)]"
      : rank === 1
        ? "text-[color:var(--accent-podium-2)]"
        : "text-[color:var(--accent-podium-3)]";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-10 items-start">
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
          >
            <Card
              surface="flat"
              team={entry.team}
              teamColor={entry.teamColor}
              className="p-6 sm:p-8 relative"
            >
              <div className="flex items-center gap-3 mb-6">
                <span className={`font-mono uppercase tracking-[0.18em] text-[14px] ${positionColor(rank)}`}>
                  {POSITION_LABELS[rank]}
                </span>
                <TeamColorBar
                  teamColor={entry.teamColor}
                  team={entry.team}
                  variant="solid"
                  size={isLeader ? "lg" : "md"}
                  animate="draw"
                />
              </div>
              <div className={isLeader ? "display-lg" : "display-md"}>{entry.driver}</div>
              <div className="body-sm text-[color:var(--muted)] mt-2 mb-6">
                {entry.driverFullName ?? entry.team}
              </div>
              <p className="eyebrow mb-2">Win probability</p>
              {entry.winProbability != null && entry.winProbability > 0 ? (
                <AnimatedNumber
                  value={entry.winProbability}
                  decimals={1}
                  suffix="%"
                  variant={isLeader ? "huge" : "default"}
                  className="text-[color:var(--ink)]"
                />
              ) : (
                <span className="display-md text-[color:var(--muted)]">—</span>
              )}
              {entry.gap && (
                <p className="eyebrow mt-4">
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
