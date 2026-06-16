import Image from "next/image";
import Link from "next/link";

import { ProjectCard } from "@/components/ProjectCard";
import { SeriesMarquee } from "@/components/SeriesMarquee";
import { GridPattern } from "@/components/magicui/grid-pattern";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { getMaturityCounts, getProjects } from "@/lib/registry";

export default function HomePage() {
  const projects = getProjects();
  const counts = getMaturityCounts();
  const featured = projects.filter(
    (p) => p.maturity === "production" || p.maturity === "experimental",
  );
  const marqueeItems = projects.map((p) => ({
    key: p.slug,
    sport: p.sport,
    icon: p.icon,
    accent: p.accent,
    maturity: p.maturity,
  }));

  return (
    <div>
      {/* ====================== HERO ====================== */}
      <section className="relative overflow-hidden">
        <GridPattern
          width={48}
          height={48}
          className="[mask-image:radial-gradient(60%_55%_at_50%_30%,white,transparent)] opacity-60"
        />
        <div className="shell relative flex flex-col items-center pt-24 pb-20 text-center sm:pt-32">
          <Image
            src="/brand/motorsportverse-logo.png"
            alt="MotorsportVerse"
            width={1217}
            height={414}
            priority
            className="h-auto w-full max-w-[560px] drop-shadow-[0_8px_40px_rgba(231,16,47,0.25)]"
          />
          <p className="eyebrow mt-8">Open-source motorsport AI</p>
          <h1 className="display mt-4 max-w-4xl">
            <span className="text-gradient">Predict every race.</span>
            <br />
            <span className="text-gradient-accent">One unified ecosystem.</span>
          </h1>
          <p className="lead mt-6 max-w-2xl">
            A family of open-source projects that forecast race outcomes across every category of
            motorsport — built on one shared core of calibration, simulation, and data
            infrastructure, extracted from the RaceIQ F1 flagship.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link href="/projects" className="btn-accent px-6 py-3 text-sm font-semibold">
              Explore projects
            </Link>
            <Link href="/docs" className="btn-ghost px-6 py-3 text-sm font-semibold">
              Read the docs
            </Link>
          </div>

          {/* stat strip */}
          <div className="mt-16 grid w-full max-w-3xl grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--hairline)] sm:grid-cols-4">
            <Stat value={projects.length} label="Projects" />
            <Stat value={counts.production ?? 0} label="In production" />
            <Stat value={counts.experimental ?? 0} label="Experimental" />
            <Stat value={2} label="Shared packages" />
          </div>
        </div>
      </section>

      {/* ====================== SERIES MARQUEE ====================== */}
      <section className="py-12">
        <p className="eyebrow shell mb-6 text-[var(--ink-dim)]">Spanning the grid</p>
        <SeriesMarquee items={marqueeItems} />
      </section>

      {/* ====================== FEATURED ====================== */}
      <section className="section">
        <div className="shell">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Live now</p>
              <h2 className="mt-2 text-3xl sm:text-4xl">Featured projects</h2>
            </div>
            <Link href="/projects" className="text-sm font-medium text-[var(--accent-bright)]">
              View all {projects.length} →
            </Link>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((p) => (
              <ProjectCard key={p.slug} project={p} featured />
            ))}
          </div>
        </div>
      </section>

      {/* ====================== PILLARS ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <div className="mb-10 max-w-2xl">
            <p className="eyebrow">Built once, reused everywhere</p>
            <h2 className="mt-2 text-3xl sm:text-4xl">One core. Every motorsport.</h2>
            <p className="lead mt-4">
              New sports don&apos;t start from scratch. Each implements a data source and a
              predictor — everything numerically heavy is shared.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            <Pillar
              title="motorsport-core"
              body="Plackett-Luce calibration, model registry, drift detection, A/B promotion, Elo, championship Monte Carlo, and forward-eval metrics — sport-agnostic and pip-installable."
              tag="Python package"
            />
            <Pillar
              title="motorsport-data"
              body="A canonical schema, DuckDB history store, and ingestion adapters that every project shares, so calendars, results, and predictions speak one language."
              tag="Python package"
            />
            <Pillar
              title="One template, many sports"
              body="RaceIQ F1 is the reference; F2 is the first operational expansion at ~74% reuse. F3, Formula E, IndyCar, NASCAR, WEC, Rally and more are on the grid."
              tag="Scalable by design"
            />
          </div>
        </div>
      </section>

      {/* ====================== CTA ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <div className="relative overflow-hidden rounded-[var(--radius-xl)] border border-[var(--hairline-strong)] bg-[var(--surface)] px-8 py-16 text-center sm:px-16">
            {/* subtle red glow from the top, plus a faint grid */}
            <GridPattern
              width={42}
              height={42}
              className="[mask-image:radial-gradient(70%_60%_at_50%_0%,white,transparent)] opacity-40"
            />
            <div
              className="pointer-events-none absolute inset-0"
              style={{ background: "var(--gradient-hero)" }}
              aria-hidden
            />
            <div className="relative">
              <p className="eyebrow">Open to contributors</p>
              <h2 className="mx-auto mt-3 max-w-2xl text-3xl sm:text-5xl">
                Bring your sport to the grid.
              </h2>
              <p className="lead mx-auto mt-5 max-w-xl">
                The shared core does the heavy lifting. You bring the data and the domain knowledge.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link href="/contribute" className="btn-accent px-6 py-3 text-sm font-semibold">
                  Start a project
                </Link>
                <Link href="/docs" className="btn-ghost px-6 py-3 text-sm font-semibold">
                  Architecture
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="bg-[var(--surface)] px-6 py-7 text-center">
      <div className="font-display text-4xl font-bold text-[var(--ink)]">
        <NumberTicker value={value} />
      </div>
      <div className="mt-1 text-xs uppercase tracking-wider text-[var(--ink-dim)]">{label}</div>
    </div>
  );
}

function Pillar({ title, body, tag }: { title: string; body: string; tag: string }) {
  return (
    <div className="card-surface hover-lift p-7">
      <p className="eyebrow text-[var(--ink-dim)]">{tag}</p>
      <h3 className="mt-3 font-display text-xl font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-[var(--ink-muted)]">{body}</p>
    </div>
  );
}
