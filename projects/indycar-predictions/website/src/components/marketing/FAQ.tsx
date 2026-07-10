"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern. Ported from RaceIQ F1 and reworded for IndyCar: one points race per
 * round, three track archetypes, and a season-long title. Answers stay within
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
        No. RaceIQ Indy is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        INDYCAR or any team.
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
    q: "What makes IndyCar hard to forecast?",
    a: (
      <>
        The same driver rarely excels everywhere: ovals, road courses and
        street circuits reward different skills, and the calendar splits
        between them almost evenly. On the ovals anyone can be collected by a
        wreck that wasn&rsquo;t theirs. The forecast reflects that: every
        driver carries separate oval and road/street form, a modelled
        retirement risk, and predicted finishing ranges that honestly widen
        where chaos reigns.
      </>
    ),
  },
  {
    q: "How is the champion decided?",
    a: (
      <>
        The classic way: most points after the final race wins — no playoffs,
        no resets. Every remaining round is simulated to project each
        driver&rsquo;s title odds and points range. The{" "}
        <Link href="/standings?tab=wdc" className="link-bugatti">
          standings page
        </Link>{" "}
        shows who is favoured, who is mathematically alive, and how far the
        long shots have to climb.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every race round and time-stamped, so you
        always know how recent a prediction is. &ldquo;Next up&rdquo; is the
        upcoming IndyCar race; results land as soon as they are official.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible.
        RaceIQ Indy runs on the same MotorsportVerse core that powers
        RaceIQ F1.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Race classifications, starting grids and championship standings — a
        hand-verified archive of fifteen seasons, updated after every round of
        the NTT IndyCar Series season.
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
