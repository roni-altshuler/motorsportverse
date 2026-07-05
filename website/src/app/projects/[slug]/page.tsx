import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MaturityBadge } from "@/components/MaturityBadge";
import { ProjectCard } from "@/components/ProjectCard";
import { ArchitecturePreview } from "@/components/project/ArchitecturePreview";
import { asset } from "@/lib/asset";
import { accentText } from "@/lib/color";
import { coreLabel, modelLabel, scrubTech, tagLabel } from "@/lib/labels";
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
  return { title: `${project.name} — MotorsportVerse`, description: scrubTech(project.summary) };
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
  const isScaffold = project.maturity === "in-development" || project.maturity === "concept";
  const isExperimental = project.maturity === "experimental";
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
              {project.logo ? (
                <div>
                  {/* full series wordmark lockup (e.g. RaceIQ MotoGP) */}
                  <Image
                    src={asset(project.logo)}
                    alt={project.name}
                    width={420}
                    height={102}
                    priority
                    className="h-14 w-auto sm:h-[4.5rem]"
                  />
                  <h1 className="sr-only">{project.name}</h1>
                  <p className="mono-label mt-3">
                    {project.sport} · {project.category}
                  </p>
                </div>
              ) : (
                <>
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
                    <h1 className="display text-4xl sm:text-5xl">{project.name}</h1>
                    <p className="mono-label mt-2">
                      {project.sport} · {project.category}
                    </p>
                  </div>
                </>
              )}
            </div>
            <MaturityBadge maturity={project.maturity} />
          </div>

          <p className="lead mt-8 max-w-3xl text-balance">
            {scrubTech(project.description || project.summary)}
          </p>

          {isExperimental && (
            <div
              className="mt-6 flex max-w-3xl items-start gap-3 rounded-[var(--radius-md)] border px-4 py-3.5 text-sm leading-relaxed text-[var(--ink-muted)]"
              style={{
                borderColor: "color-mix(in srgb, var(--maturity-experimental) 35%, transparent)",
                background: "color-mix(in srgb, var(--maturity-experimental) 7%, transparent)",
              }}
            >
              <span
                className="live-dot mt-1.5 shrink-0"
                style={{ ["--dot-color" as string]: "var(--maturity-experimental)" }}
                aria-hidden
              />
              <span>
                <strong className="font-semibold text-[var(--maturity-experimental)]">
                  Experimental.
                </strong>{" "}
                This product runs on the real season, but its forward accuracy is still accruing
                over live rounds — read the forecasts with that track record in mind.
              </span>
            </div>
          )}

          {isScaffold && (
            <div className="mt-6 flex max-w-3xl items-start gap-3 rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--surface)]/60 px-4 py-3.5 text-sm leading-relaxed text-[var(--ink-muted)]">
              <span
                className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full border"
                style={{ borderColor: "var(--maturity-in-development)" }}
                aria-hidden
              />
              <span>
                <strong className="font-semibold text-[var(--maturity-in-development)]">
                  Scaffolded.
                </strong>{" "}
                The project tree is real and lives in the monorepo — no forecasts publish until its
                two seams are implemented. The architecture preview below shows exactly what it
                inherits.
              </span>
            </div>
          )}

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
            {project.repo && <LinkButton href={project.repo} label="Source" accent={accent} />}
            {project.docs && <LinkButton href={project.docs} label="Docs" accent={accent} />}
          </div>
        </div>
      </section>

      {/* ====================== ARCHITECTURE PREVIEW (scaffolds) ====================== */}
      {isScaffold && (
        <section className="shell section pb-0">
          <ArchitecturePreview
            sport={project.sport}
            accent={accent}
            repo={project.repo}
            docs={project.docs}
            usesCore={project.uses_core}
          />
        </section>
      )}

      {/* ====================== AT A GLANCE ====================== */}
      <section className={`shell section ${isScaffold ? "pt-12" : ""}`}>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--line)] sm:grid-cols-4">
          <Glance label="Category" value={project.category} />
          <Glance label="Datasets" value={String((project.datasets ?? []).length)} />
          {isScaffold ? (
            <Glance label="Seams to implement" value="2" />
          ) : (
            <Glance label="Model components" value={String((project.models ?? []).length)} />
          )}
          <Glance label="Core modules" value={String((project.uses_core ?? []).length)} />
        </div>

        <div className="mt-12 grid gap-5 lg:grid-cols-2">
          <MetaList title="Datasets" items={project.datasets} accent={accent} />
          <MetaList
            title="Model components"
            items={(project.models ?? []).map(modelLabel)}
            accent={accent}
          />
          <MetaList
            title="Shared core modules"
            items={(project.uses_core ?? []).map(coreLabel)}
            accent={accent}
          />
          <MetaList title="Tags" items={(project.tags ?? []).map(tagLabel)} accent={accent} />
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
      style={{
        color: accentText(accent),
        borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
      }}
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
}: {
  title: string;
  items?: string[];
  accent: string;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card-premium p-6">
      <h3 className="mono-label">{title}</h3>
      <ul className="mt-4 flex flex-wrap gap-2">
        {items.map((it) => (
          <li
            key={it}
            className="rounded-full border bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--ink-muted)]"
            style={{ borderColor: `color-mix(in srgb, ${accent} 24%, var(--line))` }}
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
