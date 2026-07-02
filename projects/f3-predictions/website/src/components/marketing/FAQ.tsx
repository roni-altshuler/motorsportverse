"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for F3: spec series, two races
 * per round, FIA Formula 3. Answers stay within the tech-stack scrub policy —
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
        No. RaceIQ F3 is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        Formula 3, the FIA, or any team.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing order is graded against the official
        classification once each race is over — both the sprint and the feature
        race of every round. The live numbers are published in full on the{" "}
        <Link href="/accuracy" className="link-bugatti">
          accuracy report
        </Link>
        , including the races where the model got it wrong.
      </>
    ),
  },
  {
    q: "Why is Formula 3 a good fit for a model?",
    a: (
      <>
        F3 is a spec series — every team runs the same chassis, engine and tyres.
        With the machinery equalised, the signal that remains is driver form and
        racecraft, which is exactly what a skill-based forecast is built to read.
        The reversed-grid sprint and the merit-grid feature race are modelled
        separately, because they reward very different things.
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
        F3 runs on the same MotorsportVerse core that powers RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Sprint and feature race results, starting grids and championship
        standings, ingested after every round of the FIA Formula 3 season.
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
