"use client";

/**
 * FeatureOutcomes — benefits framed as outcomes, each a full-card link into the
 * real product surface that delivers it. Reuses BentoCard for the Bugatti card
 * shell (hairline border + `hover-lift-premium`); the content is wrapped in a
 * single `<Link>` so the whole card is one keyboard-focusable target with a
 * focus-visible ring (avoids the hover-only CTA accessibility gap).
 */
import Link from "next/link";
import { motion } from "framer-motion";
import { Trophy, TrendingUp, Target, CalendarRange } from "lucide-react";

import { BentoGrid, BentoCard } from "@/components/magicui/bento-grid";
import { fadeUp, staggerContainer } from "@/lib/motion";

interface Outcome {
  Icon: React.ComponentType<{ className?: string }>;
  name: string;
  description: string;
  href: string;
  cta: string;
  span: string;
}

const OUTCOMES: Outcome[] = [
  {
    Icon: Trophy,
    name: "See who reaches the podium — before lights out",
    description:
      "Win, podium and full-classification probabilities for every car, refreshed across the weekend.",
    href: "/calendar",
    cta: "Open the next race",
    span: "md:col-span-2",
  },
  {
    Icon: TrendingUp,
    name: "Track the title fight",
    description:
      "Drivers' and constructors' standings with projected points past the live cursor.",
    href: "/standings",
    cta: "View standings",
    span: "md:col-span-1",
  },
  {
    Icon: Target,
    name: "See how every call held up",
    description:
      "Post-race grading per round — no forecast disappears once the result is in.",
    href: "/accuracy",
    cta: "Read the accuracy report",
    span: "md:col-span-1",
  },
  {
    Icon: CalendarRange,
    name: "Read every circuit on the calendar",
    description:
      "All Grands Prix at a glance with live status, then a deep dive per round.",
    href: "/calendar",
    cta: "Browse the season",
    span: "md:col-span-2",
  },
];

export default function FeatureOutcomes() {
  return (
    <section
      aria-labelledby="features-heading"
      className="mx-auto max-w-7xl px-6 lg:px-10 section-bugatti"
    >
      <div className="mb-10 max-w-2xl">
        <p className="eyebrow mb-2">What you get</p>
        <h2 id="features-heading" className="display-md">
          Every read, one tap away
        </h2>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: "-80px" }}
      >
        <BentoGrid className="auto-rows-[15rem] md:grid-cols-3">
          {OUTCOMES.map((o) => (
            <motion.div
              key={o.name}
              variants={fadeUp}
              className={`col-span-3 ${o.span}`}
            >
              <BentoCard className="h-full">
                <Link
                  href={o.href}
                  aria-label={`${o.name} — ${o.cta}`}
                  className="group/card flex h-full flex-col justify-between p-6 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[color:var(--ink)]"
                >
                  <o.Icon className="h-9 w-9 text-[color:var(--muted)] transition-colors duration-300 group-hover/card:text-[color:var(--ink)]" />
                  <div>
                    <h3 className="title-md text-[color:var(--ink)]">{o.name}</h3>
                    <p className="body-sm mt-2 max-w-md text-[color:var(--body)]">
                      {o.description}
                    </p>
                    <span className="mt-4 inline-block font-mono text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)] transition-colors duration-300 group-hover/card:text-[color:var(--ink)]">
                      {o.cta} →
                    </span>
                  </div>
                </Link>
              </BentoCard>
            </motion.div>
          ))}
        </BentoGrid>
      </motion.div>
    </section>
  );
}
