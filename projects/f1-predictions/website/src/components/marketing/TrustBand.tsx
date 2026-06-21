"use client";

/**
 * TrustBand — honest, understated credibility band.
 *
 * Methodology/provenance forward; the real backtested metrics sit secondary
 * and are clearly labelled backtest vs current-season (never blended — see the
 * honesty rule in CLAUDE.md / TrustStats). No testimonials, user counts, or
 * fabricated logos. Numbers come from build-time props (TrustStats).
 */
import Link from "next/link";
import { motion } from "framer-motion";

import type { TrustStats } from "@/types";
import { Stat } from "@/components/ui/Stat";
import { Marquee } from "@/components/magicui/marquee";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { fadeUp, staggerContainer } from "@/lib/motion";

function MetricValue({
  value,
  suffix,
  prefix,
  decimalPlaces = 0,
}: {
  value: number;
  suffix?: string;
  prefix?: string;
  decimalPlaces?: number;
}) {
  return (
    <span>
      {prefix}
      <NumberTicker value={value} decimalPlaces={decimalPlaces} />
      {suffix}
    </span>
  );
}

export default function TrustBand({ trustStats }: { trustStats: TrustStats }) {
  const { backtest, currentSeason, provenance } = trustStats;

  // Nothing honest to show → render nothing rather than fabricate.
  if (!backtest && !currentSeason) return null;

  const seasonsLabel = backtest?.seasons?.length
    ? backtest.seasons.join("–")
    : null;

  const provenanceChips = [
    "FastF1 telemetry",
    "Ergast / Jolpica · 1950–2025",
    backtest?.gradedRows
      ? `${backtest.gradedRows.toLocaleString("en-US")} graded driver-rows`
      : null,
    "Open methodology",
    "Open source",
  ].filter(Boolean) as string[];

  return (
    <section
      aria-labelledby="trust-heading"
      className="mx-auto max-w-7xl px-6 lg:px-10 py-16 sm:py-20"
    >
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: "-80px" }}
        className="max-w-3xl"
      >
        <motion.p variants={fadeUp} className="eyebrow mb-3">
          Track record
        </motion.p>
        <motion.h2 variants={fadeUp} id="trust-heading" className="display-md mb-4">
          Graded against every result
        </motion.h2>
        <motion.p
          variants={fadeUp}
          className="body-md text-[color:var(--body)] max-w-2xl"
        >
          Every forecast is scored against the official classification once the
          chequered flag drops — no cherry-picking. The figures below are
          out-of-sample: the model never saw these races during training.
        </motion.p>
      </motion.div>

      {backtest && (
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-80px" }}
          className="mt-10 grid grid-cols-2 gap-px md:grid-cols-4"
        >
          <motion.div variants={fadeUp}>
            <Stat
              label="Mean error"
              value={<MetricValue value={backtest.maePositions} decimalPlaces={2} />}
              hint={
                backtest.rounds
                  ? `places off · ${backtest.rounds} GPs backtested`
                  : "places off · backtested"
              }
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <Stat
              label="Within 3 places"
              value={
                <MetricValue
                  value={backtest.within3Rate * 100}
                  suffix="%"
                  decimalPlaces={1}
                />
              }
              hint={seasonsLabel ? `of finishers · ${seasonsLabel}` : "of finishers"}
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <Stat
              label="Podium hit-rate"
              value={
                <MetricValue
                  value={backtest.podiumHitRate * 100}
                  suffix="%"
                  decimalPlaces={1}
                />
              }
              hint="top-3 picks that landed"
            />
          </motion.div>
          <motion.div variants={fadeUp}>
            <Stat
              tone="positive"
              label="vs. baseline"
              value={
                <MetricValue
                  value={backtest.maeImprovementVsBaseline * 100}
                  prefix="−"
                  suffix="%"
                  decimalPlaces={0}
                />
              }
              hint="lower error than qualifying pace alone"
            />
          </motion.div>
        </motion.div>
      )}

      {currentSeason?.accuracyPct != null && (
        <p className="mt-6 body-sm text-[color:var(--muted)]">
          <span className="font-mono uppercase tracking-[0.14em] text-[color:var(--body-strong)]">
            This season, live:
          </span>{" "}
          {currentSeason.accuracyPct.toFixed(1)}% podium &amp; points accuracy — how
          often the model puts the right drivers on the podium and in the points —
          across {currentSeason.roundsGraded}{" "}
          {currentSeason.roundsGraded === 1 ? "round" : "rounds"} graded so far.
        </p>
      )}

      <div className="mt-10 border-y border-[color:var(--hairline)]">
        <Marquee pauseOnHover className="[--duration:50s] py-3" aria-hidden>
          {provenanceChips.map((chip) => (
            <span
              key={chip}
              className="mx-4 inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)]"
            >
              <span
                className="inline-block h-1 w-1 rounded-full bg-[color:var(--hairline-strong)]"
                aria-hidden
              />
              {chip}
            </span>
          ))}
        </Marquee>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Link href="/accuracy" className="link-bugatti button-label text-[12px]">
          See the full accuracy report →
        </Link>
        {provenance.generatedAt && (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
            Updated {new Date(provenance.generatedAt).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </span>
        )}
      </div>
    </section>
  );
}
