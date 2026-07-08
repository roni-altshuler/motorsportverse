"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for Formula E: one race per
 * round, street vs circuit venues, doubleheader weekends. Answers stay within
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
        No. RaceIQ Formula E is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        Formula E, the FIA, or any team.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing order is graded against the official
        classification once each E-Prix is over. The live numbers are published
        in full on the{" "}
        <Link href="/accuracy" className="link-bugatti">
          accuracy report
        </Link>
        , including the races where the model got it wrong — and the current
        health warnings sit right beside the wins.
      </>
    ),
  },
  {
    q: "What makes Formula E hard to forecast?",
    a: (
      <>
        Most races run between walls on temporary street circuits, where grid
        position, energy management and safety cars can turn a race on its head
        — Shanghai was won from P19 this season. The forecast reflects that:
        probabilities are tuned separately for street and permanent circuits,
        and the predicted finishing ranges honestly widen where chaos reigns.
      </>
    ),
  },
  {
    q: "How do doubleheader weekends work?",
    a: (
      <>
        Several venues host two full championship rounds back-to-back — Jeddah,
        Berlin, Monaco, Shanghai, Tokyo, London. Each race is forecast and
        graded as its own round, and the{" "}
        <Link href="/calendar" className="link-bugatti">
          calendar
        </Link>{" "}
        pairs them so the weekend reads as one story.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every race round and time-stamped, so you
        always know how recent a prediction is. &ldquo;Next up&rdquo; is the
        upcoming E-Prix; results land as soon as they are official.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible.
        RaceIQ Formula E runs on the same MotorsportVerse core that powers
        RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Race results, starting grids and championship standings, ingested after
        every round of the ABB FIA Formula E World Championship season.
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
