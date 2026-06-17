"use client";

/**
 * EcosystemDiagram — animated dataflow showing how the shared packages sit
 * beneath every sport: data sources → motorsport-data → motorsport-core →
 * sport projects. Built on the existing AnimatedBeam primitive.
 *
 * Beams are decorative (aria-hidden) and respect prefers-reduced-motion via
 * the global media query that neutralizes framer transitions.
 */

import Image from "next/image";
import { createRef, useCallback, useMemo, useRef, type RefObject } from "react";
import { motion } from "framer-motion";

import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { asset } from "@/lib/asset";
import { fadeUp } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";

interface SportNode {
  slug: string;
  sport: string;
  icon?: string;
  accent: string;
}

export function EcosystemDiagram({ sports }: { sports: SportNode[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dataRef = useRef<HTMLDivElement>(null);
  const dataPkgRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<HTMLDivElement>(null);

  const shownSports = useMemo(() => sports.slice(0, 5), [sports]);
  // Stable per-sport refs (identity preserved across renders).
  const sportRefs = useRef<RefObject<HTMLDivElement | null>[]>([]);
  if (sportRefs.current.length !== shownSports.length) {
    sportRefs.current = shownSports.map(() => createRef<HTMLDivElement>());
  }

  // Failsafe reveal; merge its ref with the beam container ref (one node).
  const { ref: revealRef, shown } = useReveal("-80px");
  const setContainer = useCallback(
    (node: HTMLDivElement | null) => {
      containerRef.current = node;
      revealRef.current = node;
    },
    [revealRef],
  );

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate={shown ? "visible" : "hidden"}
      ref={setContainer}
      className="card-premium relative mx-auto grid max-w-4xl grid-cols-3 items-center gap-6 overflow-hidden p-8 sm:p-12"
    >
      <div className="bg-grid bg-grid-fade pointer-events-none absolute inset-0 opacity-40" />

      {/* Column 1: data sources */}
      <div className="relative z-10 flex flex-col items-start gap-3">
        <span className="mono-label">Sources</span>
        <DiagramNode innerRef={dataRef} label="FastF1 · Jolpica" tone="data" />
        <DiagramNode label="Official timing" tone="data" />
        <DiagramNode label="Scraped results" tone="data" />
      </div>

      {/* Column 2: shared packages */}
      <div className="relative z-10 flex flex-col items-center gap-4">
        <DiagramNode innerRef={dataPkgRef} label="motorsport-data" tone="pkg" strong />
        <DiagramNode innerRef={coreRef} label="motorsport-core" tone="core" strong />
      </div>

      {/* Column 3: sport projects */}
      <div className="relative z-10 flex flex-col items-end gap-2.5">
        <span className="mono-label">Sports</span>
        {shownSports.map((s, i) => (
          <DiagramNode
            key={s.slug}
            innerRef={sportRefs.current[i]}
            label={s.sport}
            icon={s.icon}
            accent={s.accent}
            tone="sport"
          />
        ))}
      </div>

      {/* Beams: sources → data → core → sports */}
      <AnimatedBeam
        containerRef={containerRef}
        fromRef={dataRef}
        toRef={dataPkgRef}
        duration={4}
        gradientStartColor="#6aa6ff"
        gradientStopColor="#38e1c6"
        pathColor="rgba(255,255,255,0.06)"
      />
      <AnimatedBeam
        containerRef={containerRef}
        fromRef={dataPkgRef}
        toRef={coreRef}
        duration={3}
        gradientStartColor="#38e1c6"
        gradientStopColor="#ff5168"
        pathColor="rgba(255,255,255,0.06)"
      />
      {shownSports.map((s, i) => (
        <AnimatedBeam
          key={s.slug}
          containerRef={containerRef}
          fromRef={coreRef}
          toRef={sportRefs.current[i]}
          duration={4}
          delay={i * 0.35}
          curvature={(i - 2) * 22}
          gradientStartColor="#ff5168"
          gradientStopColor={s.accent}
          pathColor="rgba(255,255,255,0.06)"
        />
      ))}
    </motion.div>
  );
}

function DiagramNode({
  label,
  icon,
  accent,
  tone,
  strong = false,
  innerRef,
}: {
  label: string;
  icon?: string;
  accent?: string;
  tone: "data" | "pkg" | "core" | "sport";
  strong?: boolean;
  innerRef?: React.Ref<HTMLDivElement>;
}) {
  const ring =
    tone === "core"
      ? "var(--accent-line)"
      : tone === "pkg"
        ? "rgba(56,225,198,0.4)"
        : "var(--line-strong)";
  return (
    <div
      ref={innerRef}
      className="z-10 flex items-center gap-2 rounded-[var(--radius-md)] border bg-[var(--surface-2)] px-3 py-2 text-xs font-medium text-[var(--ink)] shadow-[var(--shadow-sm)]"
      style={{
        borderColor: ring,
        boxShadow: strong ? "var(--glow-accent-subtle)" : "var(--shadow-sm)",
      }}
    >
      {icon && (
        <Image src={asset(icon)} alt="" width={16} height={16} className="h-4 w-4 shrink-0" />
      )}
      {accent && !icon && (
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent }} />
      )}
      <span className={strong ? "font-mono tracking-wide" : ""}>{label}</span>
    </div>
  );
}
