"use client";

/**
 * TechnicalCredibility — sophistication signalled honestly, without naming
 * algorithms (tech-stack scrub policy). Ported from RaceIQ F1 and reworded for
 * IndyCar: reliability, freshness, reproducibility, openness, and the shared
 * MotorsportVerse core. Freshness comes in as a build-time prop; FE has no
 * 1950-onward archive or telemetry, so those claims are dropped.
 */
import { motion } from "framer-motion";
import { RefreshCw, Clock, GitBranch, Layers } from "lucide-react";

import { GridPattern } from "@/components/magicui/grid-pattern";
import { fadeUp, staggerContainer } from "@/lib/motion";

interface Pillar {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}

export interface TechnicalCredibilityProps {
  generatedAt?: string | null;
  roundsGraded?: number;
}

export default function TechnicalCredibility({
  generatedAt,
  roundsGraded,
}: TechnicalCredibilityProps) {
  const freshness = generatedAt
    ? new Date(generatedAt).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  const pillars: Pillar[] = [
    {
      Icon: RefreshCw,
      title: "Re-trained every round",
      body: "An automated pipeline folds in the latest race result before the next round — recent form and grid position, no manual intervention.",
    },
    {
      Icon: Clock,
      title: "Time-stamped forecasts",
      body: freshness
        ? `Every forecast carries the moment it was generated, so freshness is never ambiguous. Last refreshed ${freshness}.`
        : "Every forecast carries the moment it was generated, so you always know exactly how fresh it is.",
    },
    {
      Icon: GitBranch,
      title: "Open methodology, open source",
      body: "The full pipeline and the exact accuracy scoring are public on GitHub — every number on this site is reproducible.",
    },
    {
      Icon: Layers,
      title: "One MotorsportVerse core",
      body: roundsGraded
        ? `Built on the same motorsport-core that powers RaceIQ F1, with ${roundsGraded} IndyCar ${roundsGraded === 1 ? "round" : "rounds"} graded so far this season.`
        : "Built on the same motorsport-core that powers RaceIQ F1 — one engine, tuned for a championship raced between the walls.",
    },
  ];

  return (
    <section
      aria-labelledby="tech-heading"
      className="relative overflow-hidden border-y border-[color:var(--hairline)]"
    >
      <GridPattern
        width={48}
        height={48}
        className="opacity-[0.05] [mask-image:radial-gradient(ellipse_at_center,white,transparent_80%)]"
      />
      <div className="relative mx-auto max-w-7xl px-6 lg:px-10 py-20 sm:py-24">
        <div className="mb-12 max-w-2xl">
          <p className="eyebrow mb-2">Under the hood</p>
          <h2 id="tech-heading" className="display-md">
            Built to be checked
          </h2>
          <p className="body-md mt-4 text-[color:var(--body)]">
            No black box, no cherry-picked highlights. The system is automated,
            time-stamped and open — so you can verify every claim yourself.
          </p>
        </div>

        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          viewport={{ once: true, margin: "-80px" }}
          className="grid gap-px sm:grid-cols-2 lg:grid-cols-4"
        >
          {pillars.map((p) => (
            <motion.div
              key={p.title}
              variants={fadeUp}
              className="border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-6"
            >
              <p.Icon className="h-7 w-7 text-[color:var(--muted)]" />
              <h3 className="title-sm mt-5 text-[color:var(--ink)]">{p.title}</h3>
              <p className="body-sm mt-3 text-[color:var(--body)]">{p.body}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
