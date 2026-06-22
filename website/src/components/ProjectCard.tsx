import Image from "next/image";
import Link from "next/link";

import { MaturityBadge } from "@/components/MaturityBadge";
import { asset } from "@/lib/asset";
import type { Project } from "@/types/registry";

export function ProjectCard({ project, featured = false }: { project: Project; featured?: boolean }) {
  const accent = project.accent || "var(--accent)";
  return (
    <Link
      href={`/projects/${project.slug}`}
      className="group card-surface card-pop relative block overflow-hidden p-5"
      style={{ ["--team-color" as string]: accent }}
    >
      {/* accent top edge */}
      <span
        className="absolute inset-x-0 top-0 h-[2px] opacity-60 transition-opacity group-hover:opacity-100"
        style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
        aria-hidden
      />
      {/* hover sheen */}
      <span
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ background: `radial-gradient(80% 60% at 50% 0%, ${accent}1f 0%, transparent 70%)` }}
        aria-hidden
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {project.icon ? (
            <Image
              src={asset(project.icon)}
              alt=""
              width={featured ? 48 : 40}
              height={featured ? 48 : 40}
              className={featured ? "h-12 w-12" : "h-10 w-10"}
            />
          ) : (
            <span
              className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] text-sm font-bold"
              style={{ color: accent, backgroundColor: `color-mix(in srgb, ${accent} 16%, transparent)` }}
            >
              {project.sport.slice(0, 2).toUpperCase()}
            </span>
          )}
          <div>
            <h3 className="font-display text-lg font-semibold leading-tight text-[var(--ink)]">
              {project.name}
            </h3>
            <p className="text-xs uppercase tracking-wider text-[var(--ink-dim)]">{project.sport}</p>
          </div>
        </div>
        <MaturityBadge maturity={project.maturity} />
      </div>

      <p className="relative mt-4 text-sm leading-relaxed text-[var(--ink-muted)]">
        {project.summary}
      </p>

      {project.tags && project.tags.length > 0 && (
        <div className="relative mt-4 flex flex-wrap gap-1.5">
          {project.tags.slice(0, 3).map((t) => (
            <span
              key={t}
              className="rounded-full border border-[var(--hairline)] px-2 py-0.5 text-[11px] text-[var(--ink-dim)]"
            >
              {t}
            </span>
          ))}
        </div>
      )}

      <span
        className="relative mt-5 inline-flex items-center gap-1 text-sm font-medium transition-transform group-hover:translate-x-1"
        style={{ color: accent }}
      >
        Explore project
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </Link>
  );
}
