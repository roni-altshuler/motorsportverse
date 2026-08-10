"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for MotoGP: two races per round
 * (Sprint + Grand Prix). Answers stay within the tech-stack scrub policy —
 * outcomes, not algorithms — and route the reader to the page that proves each
 * claim. No JS, full keyboard + screen-reader support, zero hydration cost.
 */
import Link from "next/link";
import { motion } from "framer-motion";

import { fadeUp, staggerContainer } from "@/lib/motion";

interface QA {
  q: string;
  a: React.ReactNode;
}

const FAQS: QA[] = [
  {
    q: "Is this betting or gambling advice?",
    a: (
      <>
        No. RaceIQ MotoGP is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        MotoGP, Dorna, the FIM, or any team.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing order is graded against the official
        classification once each race is over — both the sprint and the
        Grand Prix of every round. The live numbers are published in full on the{" "}
        <Link href="/accuracy" className="link-bugatti">
          accuracy report
        </Link>
        , including the races where the model got it wrong.
      </>
    ),
  },
  {
    q: "Why is MotoGP a good fit for a model?",
    a: (
      <>
        MotoGP packs a deep field of world-class riders into a tight, repeatable
        format — a Saturday sprint and a Sunday Grand Prix off the same grid, at
        the same circuits every year. Rider form, qualifying position and
        head-to-head history carry a strong, learnable signal, and the two races
        are modelled separately because they reward slightly different things.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every race round and time-stamped, so you
        always know how recent a prediction is. &ldquo;Next up&rdquo; is the
        upcoming round; results land for both races as soon as they are official.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible. RaceIQ
        MotoGP runs on the same MotorsportVerse core that powers RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Sprint and Grand Prix results, starting grids and championship
        standings, ingested after every round of the MotoGP season.
      </>
    ),
  },
];

export default function FAQ() {
  return (
    <section
      aria-labelledby="faq-heading"
      className="mx-auto max-w-4xl px-6 lg:px-10 section-bugatti"
    >
      <div className="mb-10 max-w-2xl">
        <p className="eyebrow mb-2">Questions</p>
        <h2 id="faq-heading" className="display-md">
          Good to know
        </h2>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        viewport={{ once: true, margin: "-80px" }}
      >
        {FAQS.map((item) => (
          <motion.details key={item.q} variants={fadeUp} className="deep-dive-section">
            <summary className="deep-dive-summary">{item.q}</summary>
            <div className="deep-dive-section-body">
              <p className="body-md text-[color:var(--body)]">{item.a}</p>
            </div>
          </motion.details>
        ))}
      </motion.div>
    </section>
  );
}
