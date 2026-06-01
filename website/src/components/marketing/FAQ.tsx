"use client";

/**
 * FAQ — native <details>/<summary> styled via the shared `.deep-dive-section`
 * pattern (same as the race-detail Deep Dive). Native disclosure means full
 * keyboard + screen-reader support with no JS and no animation node to guard,
 * and it renders correctly in the static export with no hydration cost.
 *
 * Answers stay within the tech-stack scrub policy — outcomes, not algorithms —
 * and route the reader to the page that proves each claim.
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
        No. RaceIQ is a personal project published for education and
        entertainment. The forecasts are model outputs and should not be used
        for betting or any form of gambling. The project is not affiliated with
        Formula 1, the FIA, or any constructor.
      </>
    ),
  },
  {
    q: "How accurate is it, really?",
    a: (
      <>
        Every predicted finishing position is graded against the official
        classification once a race is over — a hit lands within three places of
        the actual result. The backtested and live numbers are published in full
        on the{" "}
        <Link href="/accuracy" className="link-bugatti">
          accuracy report
        </Link>
        , including the rounds where the model got it wrong.
      </>
    ),
  },
  {
    q: "How fresh are the forecasts?",
    a: (
      <>
        Forecasts are regenerated every Grand Prix weekend and time-stamped, so
        you always know how recent a prediction is. &ldquo;Live&rdquo; means a
        session — practice, qualifying or the race — is happening as you read.
      </>
    ),
  },
  {
    q: "Is it open source?",
    a: (
      <>
        Yes. The full data pipeline, the model, and the exact accuracy scoring
        are public on GitHub, so every figure on this site is reproducible.
      </>
    ),
  },
  {
    q: "What data feeds the model?",
    a: (
      <>
        Race results, session telemetry, weather and championship standings,
        ingested each weekend — grounded in historical results reaching back to
        1950.
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
        whileInView="visible"
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
