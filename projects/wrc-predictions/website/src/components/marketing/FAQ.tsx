"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for WRC: one classification per
 * rally, run over mixed surfaces (gravel / tarmac / snow). Answers stay within
 * the tech-stack scrub policy — outcomes, not algorithms — and route the reader
 * to the page that proves each claim. No JS, full keyboard + screen-reader
 * support, zero hydration cost.
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
        No. RaceIQ WRC is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        the WRC, the FIA, the WRC Promoter, or any team.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing order is graded against the official
        classification once the rally is over. The live numbers are published in
        full on the{" "}
        <Link href="/accuracy" className="link-bugatti">
          accuracy report
        </Link>
        , including the rallies where the model got it wrong.
      </>
    ),
  },
  {
    q: "Why is the WRC a good fit for a model?",
    a: (
      <>
        The championship pits a deep field of Rally1 crews against each other over
        a repeatable calendar, but every round changes surface — gravel, tarmac or
        snow. Recent crew form, the surface underfoot and championship position
        carry a strong, learnable signal, and reading them together is exactly the
        kind of problem a model is built for.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every round and time-stamped, so you always know
        how recent a prediction is. &ldquo;Next up&rdquo; is the upcoming rally;
        the classification lands as soon as the result is official.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible. RaceIQ
        WRC runs on the same MotorsportVerse core that powers RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Rally classifications, the surface each round is run on, and championship
        standings, ingested after every round of the WRC season.
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
