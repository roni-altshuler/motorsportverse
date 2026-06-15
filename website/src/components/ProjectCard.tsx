import Link from "next/link";

import { MaturityBadge } from "@/components/MaturityBadge";
import type { Project } from "@/types/registry";

export function ProjectCard({ project }: { project: Project }) {
  const accent = project.accent || "var(--accent)";
  return (
    <Link
      href={`/projects/${project.slug}`}
      className="group block rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5 transition-colors hover:border-[var(--hairline-strong)]"
      style={{ ["--team-color" as string]: accent }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-md)] text-sm font-bold"
            style={{
              color: accent,
              backgroundColor: `color-mix(in srgb, ${accent} 16%, transparent)`,
            }}
            aria-hidden
          >
            {project.sport.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <h3 className="text-base font-semibold text-[var(--ink)]">{project.name}</h3>
            <p className="text-xs text-[var(--ink-dim)]">{project.sport}</p>
          </div>
        </div>
        <MaturityBadge maturity={project.maturity} />
      </div>

      <p className="mt-4 text-sm leading-relaxed text-[var(--ink-muted)]">{project.summary}</p>

      {project.tags && project.tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
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
        className="mt-4 inline-block text-sm font-medium transition-transform group-hover:translate-x-0.5"
        style={{ color: accent }}
      >
        View project →
      </span>
    </Link>
  );
}
