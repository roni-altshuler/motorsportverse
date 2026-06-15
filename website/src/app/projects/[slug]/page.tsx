import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MaturityBadge } from "@/components/MaturityBadge";
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
    <div className="mx-auto max-w-4xl px-6 py-16" style={{ ["--team-color" as string]: accent }}>
      <Link href="/projects" className="text-sm text-[var(--ink-dim)] hover:text-[var(--ink)]">
        ← All projects
      </Link>

      <div className="mt-6 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span
            className="flex h-14 w-14 items-center justify-center rounded-[var(--radius-md)] text-lg font-bold"
            style={{ color: accent, backgroundColor: `color-mix(in srgb, ${accent} 16%, transparent)` }}
            aria-hidden
          >
            {project.sport.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">{project.name}</h1>
            <p className="text-[var(--ink-dim)]">
              {project.sport} · <span className="capitalize">{project.category}</span>
            </p>
          </div>
        </div>
        <MaturityBadge maturity={project.maturity} />
      </div>

      <p className="mt-8 text-lg leading-relaxed text-[var(--ink-muted)]">
        {project.description || project.summary}
      </p>

      {/* Links */}
      <div className="mt-8 flex flex-wrap gap-3">
        {project.repo && <LinkButton href={project.repo} label="Repository" accent={accent} />}
        {project.website && <LinkButton href={project.website} label="Website" accent={accent} />}
        {project.docs && <LinkButton href={project.docs} label="Docs" accent={accent} />}
      </div>

      {/* Meta grid */}
      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        <MetaList title="Datasets" items={project.datasets} />
        <MetaList title="Models" items={project.models} />
        <MetaList title="Shared core modules" items={project.uses_core} />
        <MetaList title="Tags" items={project.tags} />
      </div>

      {project.added && (
        <p className="mt-12 text-xs text-[var(--ink-dim)]">Registered {project.added}</p>
      )}
    </div>
  );
}

function LinkButton({ href, label, accent }: { href: string; label: string; accent: string }) {
  return (
    <a
      href={href}
      className="rounded-full border px-4 py-2 text-sm font-medium"
      style={{ color: accent, borderColor: `color-mix(in srgb, ${accent} 40%, transparent)` }}
    >
      {label} →
    </a>
  );
}

function MetaList({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--ink-dim)]">
        {title}
      </h3>
      <ul className="mt-3 flex flex-wrap gap-2">
        {items.map((it) => (
          <li
            key={it}
            className="rounded-full border border-[var(--hairline)] px-2.5 py-1 text-xs text-[var(--ink-muted)]"
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
