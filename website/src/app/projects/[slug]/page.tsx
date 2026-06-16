import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MaturityBadge } from "@/components/MaturityBadge";
import { GridPattern } from "@/components/magicui/grid-pattern";
import { getProject, getProjects } from "@/lib/registry";

export function generateStaticParams() {
  return getProjects().map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const project = getProject(slug);
  if (!project) return { title: "Project not found — MotorsportVerse" };
  return { title: `${project.name} — MotorsportVerse`, description: project.summary };
}

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const project = getProject(slug);
  if (!project) notFound();

  const accent = project.accent || "var(--accent)";

  return (
    <div style={{ ["--team-color" as string]: accent }}>
      {/* Header band */}
      <section className="relative overflow-hidden border-b border-[var(--hairline)]">
        <GridPattern
          width={44}
          height={44}
          className="[mask-image:radial-gradient(70%_80%_at_30%_0%,white,transparent)] opacity-50"
        />
        <span
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
        />
        <div className="shell relative py-16">
          <Link
            href="/projects"
            className="text-sm text-[var(--ink-dim)] transition-colors hover:text-[var(--ink)]"
          >
            ← All projects
          </Link>

          <div className="mt-8 flex flex-wrap items-start justify-between gap-6">
            <div className="flex items-center gap-5">
              {project.icon && (
                <Image src={project.icon} alt="" width={64} height={64} className="h-16 w-16" />
              )}
              <div>
                <h1 className="display text-5xl">{project.name}</h1>
                <p className="mt-2 text-[var(--ink-dim)]">
                  {project.sport} · <span className="capitalize">{project.category}</span>
                </p>
              </div>
            </div>
            <MaturityBadge maturity={project.maturity} />
          </div>

          <p className="lead mt-8 max-w-3xl">{project.description || project.summary}</p>

          <div className="mt-8 flex flex-wrap gap-3">
            {project.repo && <LinkButton href={project.repo} label="Repository" primary accent={accent} />}
            {project.website && <LinkButton href={project.website} label="Website" accent={accent} />}
            {project.docs && <LinkButton href={project.docs} label="Docs" accent={accent} />}
          </div>
        </div>
      </section>

      {/* Meta grid */}
      <section className="shell section">
        <div className="grid gap-5 sm:grid-cols-2">
          <MetaList title="Datasets" items={project.datasets} />
          <MetaList title="Models" items={project.models} />
          <MetaList title="Shared core modules" items={project.uses_core} />
          <MetaList title="Tags" items={project.tags} />
        </div>
        {project.added && (
          <p className="mt-10 text-xs uppercase tracking-wider text-[var(--ink-dim)]">
            Registered {project.added}
          </p>
        )}
      </section>
    </div>
  );
}

function LinkButton({
  href,
  label,
  primary = false,
  accent,
}: {
  href: string;
  label: string;
  primary?: boolean;
  accent: string;
}) {
  if (primary) {
    return (
      <a href={href} className="btn-accent px-5 py-2.5 text-sm font-semibold">
        {label} →
      </a>
    );
  }
  return (
    <a
      href={href}
      className="rounded-[var(--radius-pill)] border px-5 py-2.5 text-sm font-medium"
      style={{ color: accent, borderColor: `color-mix(in srgb, ${accent} 45%, transparent)` }}
    >
      {label} →
    </a>
  );
}

function MetaList({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card-surface p-6">
      <h3 className="eyebrow text-[var(--ink-dim)]">{title}</h3>
      <ul className="mt-4 flex flex-wrap gap-2">
        {items.map((it) => (
          <li
            key={it}
            className="rounded-full border border-[var(--hairline)] bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--ink-muted)]"
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
