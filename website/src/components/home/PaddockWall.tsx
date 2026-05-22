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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
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
              className="p-4 flex items-center gap-3 h-full"
            >
              <span className="font-mono font-tabular text-sm text-[color:var(--text-muted)] w-6">
                {i + 1}
              </span>
              <TeamColorBar
                teamColor={entry.teamColor}
                team={entry.team}
                variant="gradient"
                size="md"
              />
              <div className="flex-1 min-w-0">
                <p className="font-bold truncate">{entry.name}</p>
                {entry.subtitle && (
                  <p className="text-xs text-[color:var(--text-muted)] truncate">{entry.subtitle}</p>
                )}
              </div>
              <AnimatedNumber
                value={entry.points}
                decimals={0}
                suffix="pt"
                variant="compact"
                className="text-[color:var(--text-primary)]"
              />
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
