"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for NASCAR: one points race per
 * round, four track archetypes, stage racing and the Chase. Answers stay within
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
        No. RaceIQ NASCAR is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        NASCAR or any team.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing order is graded against the official
        classification once each race is over. The live numbers are published
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
    q: "What makes NASCAR hard to forecast?",
    a: (
      <>
        Forty-car fields, pack racing and cautions. At Daytona and Talladega
        anyone in the draft can win — and anyone can be collected by a wreck
        that wasn&rsquo;t theirs. The forecast reflects that: probabilities are
        tuned separately for the four track types, every driver carries a
        modelled retirement risk, and the predicted finishing ranges honestly
        widen where chaos reigns.
      </>
    ),
  },
  {
    q: "How do stages and the Chase work?",
    a: (
      <>
        Every race runs in three stages, and the top ten of each stage score
        championship points on the spot. After 26 regular-season races, the top
        sixteen drivers enter the ten-race Chase playoff that decides the title.
        The{" "}
        <Link href="/standings?tab=wdc" className="link-bugatti">
          standings page
        </Link>{" "}
        draws today&rsquo;s playoff cut line and every driver&rsquo;s odds of
        making it — and winning it all.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every race round and time-stamped, so you
        always know how recent a prediction is. &ldquo;Next up&rdquo; is the
        upcoming Cup race; results land as soon as they are official.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible.
        RaceIQ NASCAR runs on the same MotorsportVerse core that powers
        RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Race results, stage results, starting grids and championship standings,
        ingested after every round of the NASCAR Cup Series season.
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
