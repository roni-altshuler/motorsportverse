"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/Card";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import TeamColorBar from "@/components/ui/TeamColorBar";
import { fadeUp } from "@/lib/motion";

interface Entry {
  name: string;
  subtitle?: string;
  team: string;
  teamColor: string;
  points: number;
}

interface PaddockWallProps {
  title: string;
  entries: Entry[];
  href?: string;
  limit?: number;
}

/**
 * Compact paddock-style standings wall.  Cards stack content vertically
 * so the big points number always sits inside the card on every
 * breakpoint.
 */
export default function PaddockWall({ title, entries, href, limit = 5 }: PaddockWallProps) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-xl font-black tracking-tight">{title}</h2>
        {href && (
          <a
            href={href}
            className="text-sm font-semibold text-[color:var(--accent-live)] hover:underline"
          >
            All →
          </a>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {entries.slice(0, limit).map((entry, i) => (
          <motion.div
            key={entry.name}
            custom={i}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "0px 0px -10% 0px" }}
            variants={fadeUp}
          >
            <Card
              surface="paddock"
              team={entry.team}
              teamColor={entry.teamColor}
              className="p-3 h-full flex flex-col gap-2 min-w-0"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-tabular text-2xl font-black text-[color:var(--text-muted)]">
                  {i + 1}
                </span>
                <TeamColorBar
                  teamColor={entry.teamColor}
                  team={entry.team}
                  variant="gradient"
                  size="sm"
                />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-bold truncate">{entry.name}</p>
                {entry.subtitle && (
                  <p className="text-[11px] text-[color:var(--text-muted)] truncate">
                    {entry.subtitle}
                  </p>
                )}
              </div>
              <div className="mt-auto pt-2 border-t border-[color:var(--border)] flex items-baseline justify-between gap-2">
                <span className="hud-kicker text-[9px]">Pts</span>
                <AnimatedNumber
                  value={entry.points}
                  decimals={0}
                  variant="default"
                  className="text-lg sm:text-xl"
                />
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
