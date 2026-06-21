"use client";

/**
 * HowItWorksDiagram — the "Live data → Model → Forecast" explainer, shared by
 * the About page (`beam` variant: the original AnimatedBeam node diagram) and
 * the Home page (`scrollstory` variant: a sticky pinned visual whose active
 * step advances as the reader scrolls the steps past it).
 *
 * The scroll-story is the one genuinely new interaction pattern in this pass.
 * It is built on `framer-motion onViewportEnter` (IntersectionObserver) + CSS
 * `position: sticky` — NOT a GSAP pin — so it is robust under static export +
 * Lenis and degrades cleanly under reduced motion (the visual still tracks the
 * focused step; only the transitions are neutralised by the global guard).
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
    title: "Live F1 data",
    copy: "Race results, telemetry, weather and standings ingested every Grand Prix weekend.",
  },
  {
    Icon: Cpu,
    title: "The model",
    copy: "A learning system that re-trains as the season progresses, then weighs every car in the field.",
  },
  {
    Icon: Trophy,
    title: "Race forecast",
    copy: "Probabilities for win, podium, top six and full classification — refreshed before lights out.",
  },
];

/* ── Beam variant (About) — extracted verbatim from the original About page ── */
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
        gradientStartColor="#E10600"
        gradientStopColor="#3671C6"
      />
      <AnimatedBeam
        containerRef={diagramRef}
        fromRef={modelRef}
        toRef={forecastRef}
        duration={4}
        delay={1}
        gradientStartColor="#3671C6"
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

/* ── Scroll-story variant (Home) — sticky pinned visual + advancing steps ── */
function HowItWorksScrollStory() {
  const [active, setActive] = useState(0);

  return (
    <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
      {/* Sticky visual — reflects the active step */}
      <div className="hidden lg:block">
        <div className="sticky top-32 flex h-[60vh] flex-col justify-center">
          <StickyVisual active={active} />
        </div>
      </div>

      {/* Steps — each one claims the active slot as it enters view */}
      <motion.ol
        variants={staggerContainer}
        initial="hidden"
        whileInView="visible"
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
                  borderColor:
                    active === i ? "var(--ink)" : "var(--hairline-strong)",
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
      {/* progress rail */}
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
