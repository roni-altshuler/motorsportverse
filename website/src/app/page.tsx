import Image from "next/image";
import Link from "next/link";

import { ProjectCard } from "@/components/ProjectCard";
import { getMaturityCounts, getProjects } from "@/lib/registry";

export default function HomePage() {
  const projects = getProjects();
  const counts = getMaturityCounts();
  const featured = projects.filter(
    (p) => p.maturity === "production" || p.maturity === "in-development",
  );

  return (
    <div className="mx-auto max-w-6xl px-6">
      {/* Hero */}
      <section className="py-20 sm:py-28">
        <Image
          src="/brand/motorsportverse-logo.png"
          alt="MotorsportVerse"
          width={1217}
          height={414}
          priority
          className="mb-8 h-auto w-full max-w-xl"
        />
        <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-[var(--accent)]">
          Open-source motorsport AI
        </p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight text-[var(--ink)] sm:text-6xl">
          One ecosystem for motorsport prediction.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-[var(--ink-muted)]">
          MotorsportVerse is a family of open-source projects that forecast race
          outcomes across every category of motorsport — built on a shared core of
          calibration, evaluation, and data infrastructure extracted from the
          F1 Predictions flagship.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/projects"
            className="rounded-full px-5 py-2.5 text-sm font-semibold"
            style={{ color: "var(--accent-ink)", backgroundColor: "var(--accent)" }}
          >
            Explore projects
          </Link>
          <Link
            href="/docs"
            className="rounded-full border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-semibold text-[var(--ink)] hover:border-[var(--accent)]"
          >
            Read the docs
          </Link>
        </div>

        {/* Stat strip */}
        <div className="mt-12 flex flex-wrap gap-8 border-t border-[var(--hairline)] pt-8">
          <Stat label="Projects" value={String(projects.length)} />
          <Stat label="Production" value={String(counts.production ?? 0)} />
          <Stat label="In development" value={String(counts["in-development"] ?? 0)} />
          <Stat label="Shared packages" value="2" />
        </div>
      </section>

      {/* Featured */}
      <section className="pb-12">
        <div className="mb-6 flex items-end justify-between">
          <h2 className="text-2xl font-semibold text-[var(--ink)]">Featured projects</h2>
          <Link href="/projects" className="text-sm text-[var(--accent)]">
            View all →
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((p) => (
            <ProjectCard key={p.slug} project={p} />
          ))}
        </div>
      </section>

      {/* Ecosystem pitch */}
      <section className="grid gap-4 pb-24 sm:grid-cols-3">
        <Pitch
          title="motorsport-core"
          body="Calibration, model registry, drift, promotion, Elo, and forward-eval metrics — sport-agnostic and pip-installable."
        />
        <Pitch
          title="motorsport-data"
          body="A canonical schema, history store, and ingestion adapters that every project shares."
        />
        <Pitch
          title="One template, many sports"
          body="F1 is the reference. Each new sport implements a DataSource and a Predictor — everything else is reused."
        />
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-3xl font-bold text-[var(--ink)]">{value}</div>
      <div className="text-xs uppercase tracking-wider text-[var(--ink-dim)]">{label}</div>
    </div>
  );
}

function Pitch({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
      <h3 className="text-base font-semibold text-[var(--ink)]">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">{body}</p>
    </div>
  );
}
