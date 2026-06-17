"use client";

/**
 * ShowcaseRail — premium "live demo" cards for the operational projects
 * (F1, F2). Each card links to the project's live dashboard and its detail
 * page, framed as a mini case study. Mouse-tracked spotlight on hover.
 */

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { useRef } from "react";

import { MaturityBadge } from "@/components/MaturityBadge";
import { asset } from "@/lib/asset";
import { fadeUp, staggerContainer } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";
import type { Project } from "@/types/registry";

export function ShowcaseRail({ projects }: { projects: Project[] }) {
  const { ref, shown } = useReveal();
  return (
    <motion.div
      ref={ref}
      className="grid gap-6 lg:grid-cols-2"
      variants={staggerContainer}
      initial="hidden"
      animate={shown ? "visible" : "hidden"}
    >
      {projects.map((p, i) => (
        <ShowcaseCard key={p.slug} project={p} index={i} />
      ))}
    </motion.div>
  );
}

function ShowcaseCard({ project, index }: { project: Project; index: number }) {
  const accent = project.accent || "var(--accent)";
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  return (
    <motion.div variants={fadeUp} custom={index}>
      <div
        ref={ref}
        onMouseMove={onMove}
        className="group card-premium edge-accent relative overflow-hidden p-7"
        style={{ ["--team-color" as string]: accent }}
      >
        {/* mouse spotlight */}
        <div
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            background: `radial-gradient(340px circle at var(--mx, 50%) var(--my, 0%), ${accent}1f, transparent 70%)`,
          }}
          aria-hidden
        />

        <div className="relative flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            {project.icon && (
              <span
                className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-md)] border"
                style={{
                  borderColor: `color-mix(in srgb, ${accent} 35%, transparent)`,
                  background: `color-mix(in srgb, ${accent} 10%, transparent)`,
                }}
              >
                <Image src={asset(project.icon)} alt="" width={34} height={34} className="h-[34px] w-[34px]" />
              </span>
            )}
            <div>
              <h3 className="font-display text-2xl font-semibold text-[var(--ink)]">{project.name}</h3>
              <p className="mono-label mt-1">{project.sport}</p>
            </div>
          </div>
          <MaturityBadge maturity={project.maturity} />
        </div>

        <p className="relative mt-5 text-sm leading-relaxed text-[var(--ink-muted)]">
          {project.summary}
        </p>

        {project.uses_core && project.uses_core.length > 0 && (
          <div className="relative mt-5 flex flex-wrap gap-1.5">
            <span className="mono-label mr-1 self-center">core</span>
            {project.uses_core.slice(0, 5).map((m) => (
              <span
                key={m}
                className="rounded-full border border-[var(--line)] bg-[var(--surface-2)] px-2.5 py-0.5 text-[11px] text-[var(--ink-dim)]"
              >
                {m}
              </span>
            ))}
          </div>
        )}

        <div className="relative mt-7 flex flex-wrap items-center gap-3">
          {project.website && (
            <a
              href={project.website}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-4 py-2 text-sm font-semibold"
              style={{ color: "var(--accent-ink)", background: accent }}
            >
              Live demo
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M7 17 17 7M9 7h8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
          )}
          <Link
            href={`/projects/${project.slug}`}
            className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] border border-[var(--line-strong)] px-4 py-2 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--ink-dim)]"
          >
            Case study →
          </Link>
        </div>
      </div>
    </motion.div>
  );
}
