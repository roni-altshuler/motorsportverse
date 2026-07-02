"use client";

/**
 * TrustBand — honest, understated credibility band, ported from RaceIQ F1.
 *
 * F1 read its numbers from a separate trust-stats JSON with a multi-season
 * backtest block. F3 has no backtest export yet, so the figures here are
 * derived at build time from the live season accuracy (rounds run, podium /
 * winner hit-rate, mean position error) and passed in as plain props. No
 * testimonials, user counts, or fabricated logos.
 */
import Link from "next/link";
import { motion } from "framer-motion";

import { Stat } from "@/components/ui/Stat";
import { Marquee } from "@/components/magicui/marquee";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { fadeUp, staggerContainer } from "@/lib/motion";

export interface TrustBandProps {
  roundsScored: number;
  totalRounds: number;
  podiumHitRate: number | null;
  winnerHitRate: number | null;
  meanPositionError: number | null;
  generatedAt?: string | null;
}

function MetricValue({
  value,
  suffix,
  decimalPlaces = 0,
}: {
  value: number;
  suffix?: string;
  decimalPlaces?: number;
}) {
  return (
    <span>
      <NumberTicker value={value} decimalPlaces={decimalPlaces} />
      {suffix}
    </span>
  );
}

export default function TrustBand({
  roundsScored,
  totalRounds,
  podiumHitRate,
  winnerHitRate,
  meanPositionError,
  generatedAt,
}: TrustBandProps) {
  // Nothing honest to show yet → render nothing rather than fabricate.
  if (roundsScored <= 0) return null;

  const provenanceChips = [
    "FIA Formula 3 results",
    "Spec series · driver-skill model",
    "Two races per round · sprint + feature",
    `${roundsScored} of ${totalRounds} rounds graded`,
    "Open methodology",
    "MotorsportVerse core",
  ];

  return (
    <section
      aria-labelledby="trust-heading"
      className="mx-auto max-w-7xl px-6 lg:px-10 py-16 sm:py-20"
    >
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
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
          chequered flag drops on both races of the round — sprint and feature —
          no cherry-picking. The figures below cover the season so far.
        </motion.p>
      </motion.div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        viewport={{ once: true, margin: "-80px" }}
        className="mt-10 grid grid-cols-2 gap-px md:grid-cols-4"
      >
        <motion.div variants={fadeUp}>
          <Stat
            label="Rounds graded"
            value={<MetricValue value={roundsScored} />}
            hint={`of ${totalRounds} on the calendar`}
          />
        </motion.div>
        <motion.div variants={fadeUp}>
          <Stat
            label="Podium hit-rate"
            value={
              podiumHitRate != null ? (
                <MetricValue value={podiumHitRate * 100} suffix="%" decimalPlaces={0} />
              ) : (
                "—"
              )
            }
            hint="top-3 picks that landed"
          />
        </motion.div>
        <motion.div variants={fadeUp}>
          <Stat
            label="Winner hit-rate"
            value={
              winnerHitRate != null ? (
                <MetricValue value={winnerHitRate * 100} suffix="%" decimalPlaces={0} />
              ) : (
                "—"
              )
            }
            hint="race wins called correctly"
          />
        </motion.div>
        <motion.div variants={fadeUp}>
          <Stat
            tone="positive"
            label="Mean error"
            value={
              meanPositionError != null ? (
                <MetricValue value={meanPositionError} decimalPlaces={1} />
              ) : (
                "—"
              )
            }
            hint="places off, on average"
          />
        </motion.div>
      </motion.div>

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
        {generatedAt && (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
            Updated{" "}
            {new Date(generatedAt).toLocaleDateString("en-US", {
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
