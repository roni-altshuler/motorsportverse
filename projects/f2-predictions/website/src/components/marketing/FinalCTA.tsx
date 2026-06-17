"use client";

/**
 * FinalCTA — the closing conversion moment, ported from RaceIQ F1. One dominant
 * primary path into the product (the next round), one quiet secondary (the
 * receipts). ShimmerButton is the sanctioned glow here; it is reduced-motion
 * guarded globally. Reworded for F2 and routed to /predictions.
 */
import Link from "next/link";
import { motion } from "framer-motion";

import { buttonVariants } from "@/components/ui/Button";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { fadeUp } from "@/lib/motion";

export default function FinalCTA() {
  return (
    <section
      aria-labelledby="cta-heading"
      className="mx-auto max-w-7xl px-6 lg:px-10 pb-24 sm:pb-32"
    >
      <motion.div
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        viewport={{ once: true, margin: "-80px" }}
        className="relative overflow-hidden border border-[color:var(--hairline)] rounded-[var(--radius-card)] bg-[color:var(--surface-card)] px-8 py-16 text-center sm:px-16 sm:py-20"
      >
        {/* Single accent hairline at the top edge — sanctioned CTA accent. */}
        <span
          aria-hidden
          className="absolute inset-x-0 top-0 h-px bg-[color:var(--accent)]"
        />

        <p className="eyebrow mb-4">Lights out</p>
        <h2 id="cta-heading" className="display-lg [font-weight:700] text-balance">
          Ready before the grid forms
        </h2>
        <p className="body-md mt-5 mx-auto max-w-xl text-[color:var(--body)]">
          Open the next-round forecast — sprint and feature — then judge it
          against the result. That is the whole deal.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link href="/predictions">
            <ShimmerButton
              background="var(--accent)"
              shimmerColor="rgba(255,255,255,0.9)"
              borderRadius="9999px"
              className="button-label h-11 !px-7 !py-0 text-[13px]"
            >
              See the next round →
            </ShimmerButton>
          </Link>
          <Link href="/accuracy" className={buttonVariants({ variant: "ghost" })}>
            How accurate is it?
          </Link>
        </div>
      </motion.div>
    </section>
  );
}
