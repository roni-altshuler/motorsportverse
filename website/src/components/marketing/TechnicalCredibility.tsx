"use client";

/**
 * TechnicalCredibility — sophistication signalled honestly, without naming
 * algorithms (tech-stack scrub policy): reliability, freshness, reproducibility
 * and openness. Reads freshness from build-time props (TrustStats); falls back
 * gracefully when a figure is unavailable.
 */
import { motion } from "framer-motion";
import { RefreshCw, Clock, GitBranch, Database } from "lucide-react";

import type { TrustStats } from "@/types";
import { GridPattern } from "@/components/magicui/grid-pattern";
import { fadeUp, staggerContainer } from "@/lib/motion";

interface Pillar {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}

export default function TechnicalCredibility({
  trustStats,
}: {
  trustStats: TrustStats;
}) {
  const freshness = trustStats.provenance.generatedAt
    ? new Date(trustStats.provenance.generatedAt).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;
  const gradedRows = trustStats.backtest?.gradedRows;

  const pillars: Pillar[] = [
    {
      Icon: RefreshCw,
      title: "Re-trained every weekend",
      body: "An automated pipeline folds in the latest race before the next Grand Prix — recent form, upgrades and weather, no manual intervention.",
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
      Icon: Database,
      title: "Decades of racing behind it",
      body: gradedRows
        ? `Grounded in ${gradedRows.toLocaleString("en-US")} graded driver-rows, with historical data reaching back to 1950.`
        : "Grounded in thousands of graded results, with historical data reaching back to 1950.",
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
          whileInView="visible"
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
