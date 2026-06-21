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

export default function PaddockWall({ title, entries, href, limit = 6 }: PaddockWallProps) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-8">
        <h2 className="display-md">{title}</h2>
        {href && (
          <a href={href} className="link-bugatti button-label">
            All
          </a>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-10">
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
              surface="flat"
              interactive
              team={entry.team}
              teamColor={entry.teamColor}
              className="p-6 h-full flex flex-col gap-4 min-w-0"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-tabular text-[14px] tracking-[0.18em] text-[color:var(--muted)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <TeamColorBar
                  teamColor={entry.teamColor}
                  team={entry.team}
                  variant="solid"
                  size="md"
                />
              </div>
              <div className="min-w-0">
                <p className="title-md truncate">{entry.name}</p>
                {entry.subtitle && (
                  <p className="eyebrow truncate mt-2">{entry.subtitle}</p>
                )}
              </div>
              <div className="mt-auto pt-4 hairline-divider-top flex items-baseline justify-between gap-2">
                <span className="eyebrow">Points</span>
                <AnimatedNumber
                  value={entry.points}
                  decimals={0}
                  variant="default"
                  className="text-[color:var(--ink)]"
                />
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
