import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MaturityBadge } from "@/components/MaturityBadge";
import { ProjectCard } from "@/components/ProjectCard";
import { asset } from "@/lib/asset";
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
  const all = getProjects();
  const related = all
    .filter((p) => p.slug !== project.slug && p.category === project.category)
    .slice(0, 3);
  const fallbackRelated = related.length
    ? related
    : all.filter((p) => p.slug !== project.slug).slice(0, 3);

  return (
    <div style={{ ["--team-color" as string]: accent }}>
      {/* ====================== CASE-STUDY HERO ====================== */}
      <section className="relative overflow-hidden border-b border-[var(--line)]">
        <div className="bg-grid bg-grid-fade pointer-events-none absolute inset-0 opacity-50" />
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: `radial-gradient(60% 50% at 30% -10%, color-mix(in srgb, ${accent} 14%, transparent), transparent 60%)`,
          }}
          aria-hidden
        />
        <span
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{ background: `linear-gradient(90deg, transparent, ${accent}, transparent)` }}
        />

        <div className="shell relative py-16 sm:py-20">
          <Link
            href="/projects"
            className="text-sm text-[var(--ink-dim)] transition-colors hover:text-[var(--ink)]"
          >
            ← All projects
          </Link>

          <div className="mt-8 flex flex-wrap items-start justify-between gap-6">
            <div className="flex items-center gap-5">
              {project.icon && (
                <span
                  className="flex h-20 w-20 items-center justify-center rounded-[var(--radius-lg)] border"
                  style={{
                    borderColor: `color-mix(in srgb, ${accent} 35%, transparent)`,
                    background: `color-mix(in srgb, ${accent} 10%, transparent)`,
                  }}
                >
                  <Image src={asset(project.icon)} alt="" width={48} height={48} className="h-12 w-12" />
                </span>
              )}
              <div>
                <h1 className="display text-5xl">{project.name}</h1>
                <p className="mono-label mt-2">
                  {project.sport} · {project.category}
                </p>
              </div>
            </div>
            <MaturityBadge maturity={project.maturity} />
          </div>

          <p className="lead mt-8 max-w-3xl text-balance">
            {project.description || project.summary}
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            {project.website && (
              <a
                href={project.website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-5 py-2.5 text-sm font-semibold"
                style={{ color: "var(--accent-ink)", background: accent }}
              >
                Live demo
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden>
                  <path d="M7 17 17 7M9 7h8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
            )}
            {project.repo && <LinkButton href={project.repo} label="Repository" accent={accent} />}
            {project.docs && <LinkButton href={project.docs} label="Docs" accent={accent} />}
          </div>
        </div>
      </section>

      {/* ====================== AT A GLANCE ====================== */}
      <section className="shell section">
        <div className="grid gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--line)] sm:grid-cols-4">
          <Glance label="Category" value={project.category} />
          <Glance label="Datasets" value={String((project.datasets ?? []).length)} />
          <Glance label="Models" value={String((project.models ?? []).length)} />
          <Glance label="Core modules" value={String((project.uses_core ?? []).length)} />
        </div>

        <div className="mt-12 grid gap-5 lg:grid-cols-2">
          <MetaList title="Datasets" items={project.datasets} accent={accent} />
          <MetaList title="Models" items={project.models} accent={accent} />
          <MetaList title="Shared core modules" items={project.uses_core} accent={accent} mono />
          <MetaList title="Tags" items={project.tags} accent={accent} />
        </div>

        {project.maintainers && project.maintainers.length > 0 && (
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <span className="mono-label">Maintained by</span>
            {project.maintainers.map((m) => (
              <a
                key={m.github ?? m.name}
                href={m.github ? `https://github.com/${m.github}` : undefined}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-[var(--line)] bg-[var(--surface-2)] px-3 py-1 text-sm text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
              >
                {m.name ?? m.github}
              </a>
            ))}
          </div>
        )}

        {project.added && (
          <p className="mono-label mt-10">Registered {project.added}</p>
        )}
      </section>

      {/* ====================== RELATED ====================== */}
      {fallbackRelated.length > 0 && (
        <section className="shell section pt-0">
          <div className="mb-8 flex items-end justify-between">
            <h2 className="text-2xl sm:text-3xl">Related projects</h2>
            <Link
              href="/projects"
              className="text-sm font-medium text-[var(--accent-text)] hover:text-[var(--accent-bright)]"
            >
              View all →
            </Link>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {fallbackRelated.map((p) => (
              <ProjectCard key={p.slug} project={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function LinkButton({ href, label, accent }: { href: string; label: string; accent: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="rounded-[var(--radius-pill)] border px-5 py-2.5 text-sm font-medium transition-colors"
      style={{ color: accent, borderColor: `color-mix(in srgb, ${accent} 45%, transparent)` }}
    >
      {label} →
    </a>
  );
}

function Glance({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--surface)] px-5 py-6">
      <div className="font-display text-2xl font-semibold capitalize text-[var(--ink)]">{value}</div>
      <div className="mono-label mt-1.5">{label}</div>
    </div>
  );
}

function MetaList({
  title,
  items,
  accent,
  mono = false,
}: {
  title: string;
  items?: string[];
  accent: string;
  mono?: boolean;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card-premium p-6">
      <h3 className="mono-label">{title}</h3>
      <ul className="mt-4 flex flex-wrap gap-2">
        {items.map((it) => (
          <li
            key={it}
            className={`rounded-full border bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--ink-muted)] ${
              mono ? "font-mono tracking-wide" : ""
            }`}
            style={{ borderColor: `color-mix(in srgb, ${accent} 24%, var(--line))` }}
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
