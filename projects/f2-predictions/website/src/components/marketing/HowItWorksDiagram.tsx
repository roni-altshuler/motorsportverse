"use client";

/**
 * HowItWorksDiagram — the "Results → Model → Forecast" explainer, ported from
 * RaceIQ F1. F2 has no telemetry, weather or pit-strategy data, so the copy is
 * reworded around what the spec series actually provides: per-round results
 * across both races, a driver-skill model, and per-race probabilities. Two
 * variants: `beam` (AnimatedBeam node diagram) and `scrollstory` (sticky pinned
 * visual whose active step advances on scroll). Both degrade cleanly under the
 * global reduced-motion guard.
 */
import { useRef, useState } from "react";
import { Database, Cpu, Trophy } from "lucide-react";
import { motion } from "framer-motion";

import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { fadeUp, staggerContainer } from "@/lib/motion";

interface Step {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  copy: string;
}

const STEPS: Step[] = [
  {
    Icon: Database,
    title: "Formula 2 results",
    copy: "Sprint and feature finishing orders, grids and championship standings ingested after every round.",
  },
  {
    Icon: Cpu,
    title: "The model",
    copy: "A driver-skill model built for a spec series — where the cars are equal, so form and racecraft carry the signal. It re-trains as the season unfolds, then weighs every car in the field.",
  },
  {
    Icon: Trophy,
    title: "Race forecast",
    copy: "Probabilities for win, podium, top six and top ten — for both the reversed-grid sprint and the merit-grid feature race.",
  },
];

/* ── Beam variant ── */
function HowItWorksBeam() {
  const diagramRef = useRef<HTMLDivElement>(null);
  const dataRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const forecastRef = useRef<HTMLDivElement>(null);
  const refs = [dataRef, modelRef, forecastRef];

  return (
    <div
      ref={diagramRef}
      className="relative grid grid-cols-3 gap-4 sm:gap-8 py-10 px-2 sm:px-8"
    >
      {STEPS.map((step, i) => (
        <DiagramNode
          key={step.title}
          innerRef={refs[i]}
          Icon={step.Icon}
          title={step.title}
          description={step.copy}
        />
      ))}

      <AnimatedBeam
        containerRef={diagramRef}
        fromRef={dataRef}
        toRef={modelRef}
        duration={4}
        gradientStartColor="#1E9BD7"
        gradientStopColor="#7DD3FC"
      />
      <AnimatedBeam
        containerRef={diagramRef}
        fromRef={modelRef}
        toRef={forecastRef}
        duration={4}
        delay={1}
        gradientStartColor="#7DD3FC"
        gradientStopColor="#FFD166"
      />
    </div>
  );
}

function DiagramNode({
  innerRef,
  Icon,
  title,
  description,
}: {
  innerRef: React.RefObject<HTMLDivElement | null>;
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div ref={innerRef} className="relative z-10 flex flex-col items-center text-center">
      <span
        className="inline-flex items-center justify-center w-14 h-14 rounded-full border mb-4"
        style={{ borderColor: "var(--hairline-strong)", background: "var(--surface-card)" }}
      >
        <Icon className="w-6 h-6 text-[color:var(--ink)]" />
      </span>
      <p className="title-sm text-[color:var(--ink)] mb-2">{title}</p>
      <p className="body-sm text-[color:var(--muted)] max-w-[200px]">{description}</p>
    </div>
  );
}

/* ── Scroll-story variant ── */
function HowItWorksScrollStory() {
  const [active, setActive] = useState(0);

  return (
    <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
      <div className="hidden lg:block">
        <div className="sticky top-32 flex h-[60vh] flex-col justify-center">
          <StickyVisual active={active} />
        </div>
      </div>

      <motion.ol
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        viewport={{ once: true, margin: "-80px" }}
        className="flex flex-col"
      >
        {STEPS.map((step, i) => (
          <motion.li
            key={step.title}
            variants={fadeUp}
            onViewportEnter={() => setActive(i)}
            viewport={{ margin: "-45% 0px -45% 0px" }}
            className="border-l border-[color:var(--hairline)] py-10 pl-8 lg:py-16"
            aria-current={active === i ? "step" : undefined}
          >
            <span className="flex items-center gap-3">
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full border font-mono text-[12px]"
                style={{
                  borderColor: active === i ? "var(--ink)" : "var(--hairline-strong)",
                  color: active === i ? "var(--ink)" : "var(--muted)",
                  transition: "color 320ms, border-color 320ms",
                }}
              >
                {i + 1}
              </span>
              <step.Icon className="h-5 w-5 text-[color:var(--muted)]" />
            </span>
            <h3 className="title-md mt-5 text-[color:var(--ink)]">{step.title}</h3>
            <p className="body-md mt-3 max-w-md text-[color:var(--body)]">{step.copy}</p>
          </motion.li>
        ))}
      </motion.ol>
    </div>
  );
}

function StickyVisual({ active }: { active: number }) {
  const step = STEPS[active];
  const StepIcon = step.Icon;
  return (
    <div className="relative border border-[color:var(--hairline)] rounded-[var(--radius-card)] bg-[color:var(--surface-card)] p-10">
      <div className="flex gap-2" aria-hidden>
        {STEPS.map((_, i) => (
          <span
            key={i}
            className="h-[2px] flex-1"
            style={{
              background: i <= active ? "var(--ink)" : "var(--hairline)",
              transition: "background 320ms",
            }}
          />
        ))}
      </div>

      <div className="mt-10 flex flex-col items-center text-center">
        <motion.span
          key={active}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.32 }}
          className="inline-flex h-20 w-20 items-center justify-center rounded-full border border-[color:var(--hairline-strong)]"
        >
          <StepIcon className="h-8 w-8 text-[color:var(--ink)]" />
        </motion.span>
        <p className="eyebrow mt-6">
          Step {active + 1} / {STEPS.length}
        </p>
        <p className="title-md mt-2 text-[color:var(--ink)]">{step.title}</p>
      </div>
    </div>
  );
}

export { HowItWorksBeam };

export default function HowItWorksDiagram({
  variant = "beam",
}: {
  variant?: "beam" | "scrollstory";
}) {
  return variant === "scrollstory" ? <HowItWorksScrollStory /> : <HowItWorksBeam />;
}
