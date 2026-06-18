import Link from "next/link";

import { CommandPaletteHint } from "@/components/landing/CommandPaletteHint";
import { EcosystemDiagram } from "@/components/landing/EcosystemDiagram";
import { FeatureBento } from "@/components/landing/FeatureBento";
import { PredictionTicker } from "@/components/landing/PredictionTicker";
import { Reveal } from "@/components/landing/Reveal";
import { ShowcaseRail } from "@/components/landing/ShowcaseRail";
import { SplineShowcase } from "@/components/landing/SplineShowcase";
import { SeriesMarquee } from "@/components/SeriesMarquee";
import { VerseHero } from "@/components/hero/VerseHero";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { getMaturityCounts, getProjects } from "@/lib/registry";
import { synthTickerRows } from "@/lib/ticker";

export default function HomePage() {
  const projects = getProjects();
  const counts = getMaturityCounts();

  const operational = projects.filter(
    (p) => p.maturity === "production" || p.maturity === "experimental",
  );
  const tickerRows = synthTickerRows(projects);

  const marqueeItems = projects.map((p) => ({
    key: p.slug,
    sport: p.sport,
    icon: p.icon,
    accent: p.accent,
    maturity: p.maturity,
  }));

  const nodeColors = projects.map((p) => p.accent || "#e7102f");

  const diagramSports = projects
    .slice()
    .sort((a, b) => {
      const rank = (m: string) => (m === "production" ? 0 : m === "experimental" ? 1 : 2);
      return rank(a.maturity) - rank(b.maturity);
    })
    .map((p) => ({ slug: p.slug, sport: p.sport, icon: p.icon, accent: p.accent || "#e7102f" }));

  const heroStats = [
    { value: String(projects.length), label: "Projects" },
    { value: String(counts.production ?? 0), label: "In production" },
    { value: String(counts.experimental ?? 0), label: "Experimental" },
    { value: "2", label: "Shared packages" },
  ];

  return (
    <div>
      {/* ====================== WEBGL HERO ====================== */}
      <VerseHero nodeColors={nodeColors} stats={heroStats} />

      {/* ====================== LIVE PREDICTION TICKER ====================== */}
      <PredictionTicker rows={tickerRows} />

      {/* ====================== SERIES MARQUEE ====================== */}
      <section className="py-14">
        <p className="mono-label shell mb-6">Spanning the grid</p>
        <SeriesMarquee items={marqueeItems} />
      </section>

      {/* ====================== ECOSYSTEM ARCHITECTURE ====================== */}
      <section className="section pt-4">
        <div className="shell">
          <Reveal className="mx-auto mb-12 max-w-2xl text-center">
            <p className="eyebrow eyebrow-accent eyebrow-tick">The architecture</p>
            <h2 className="mt-3 text-[length:var(--text-4xl)]">One core. Every motorsport.</h2>
            <p className="lead mt-4">
              Data sources flow through two shared packages into every sport. Nothing numerically
              heavy is rebuilt — each project just adds a data adapter and a predictor.
            </p>
          </Reveal>
          <EcosystemDiagram sports={diagramSports} />
        </div>
      </section>

      {/* ====================== 3D SPLINE SHOWCASE ====================== */}
      <SplineShowcase />

      {/* ====================== FEATURE BENTO ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal className="mb-10 max-w-2xl">
            <p className="eyebrow eyebrow-accent eyebrow-tick">Built once, reused everywhere</p>
            <h2 className="mt-3 text-[length:var(--text-4xl)]">The shared core</h2>
            <p className="lead mt-4">
              Calibration, simulation, drift detection, and a model registry — the hard parts,
              solved once and pip-installable.
            </p>
          </Reveal>
          <FeatureBento />
        </div>
      </section>

      {/* ====================== LIVE PROJECT SHOWCASE ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow eyebrow-accent eyebrow-tick">Live now</p>
              <h2 className="mt-3 text-[length:var(--text-4xl)]">Operational projects</h2>
            </div>
            <Link
              href="/projects"
              className="text-sm font-medium text-[var(--accent-text)] transition-colors hover:text-[var(--accent-bright)]"
            >
              View all {projects.length} →
            </Link>
          </Reveal>
          <ShowcaseRail projects={operational} />
        </div>
      </section>

      {/* ====================== CREDIBILITY RAIL ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal className="card-premium grid grid-cols-2 gap-px overflow-hidden bg-[var(--line)] sm:grid-cols-4">
            <CredStat value={projects.length} label="Sports registered" />
            <CredStat value={74} suffix="%" label="Core reuse (F2)" />
            <CredStat value={10} suffix="+" label="Shared modules" />
            <CredStat value={2} label="Live dashboards" />
          </Reveal>
        </div>
      </section>

      {/* ====================== FINAL CTA ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal>
            <div className="liquid-glass-pane relative overflow-hidden px-8 py-20 text-center sm:px-16">
              <div className="bg-grid bg-grid-fade pointer-events-none absolute inset-0 opacity-40" />
              <div
                className="pointer-events-none absolute inset-0"
                style={{ background: "var(--mesh-1)" }}
                aria-hidden
              />
              <div className="relative">
                <p className="eyebrow eyebrow-accent eyebrow-tick">Open to contributors</p>
                <h2 className="mx-auto mt-4 max-w-2xl text-[length:var(--text-4xl)] sm:text-5xl">
                  Bring your sport to the grid.
                </h2>
                <p className="lead mx-auto mt-5 max-w-xl">
                  The shared core does the heavy lifting. You bring the data and the domain
                  knowledge.
                </p>
                <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                  <Link href="/contribute" className="btn-accent px-6 py-3 text-sm font-semibold">
                    Start a project
                  </Link>
                  <Link href="/docs" className="btn-ghost px-6 py-3 text-sm font-semibold">
                    Architecture
                  </Link>
                </div>
                <CommandPaletteHint />
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}

function CredStat({ value, label, suffix }: { value: number; label: string; suffix?: string }) {
  return (
    <div className="bg-[var(--surface)] px-6 py-10 text-center">
      <div className="font-display text-4xl font-bold text-[var(--ink)]">
        <NumberTicker value={value} />
        {suffix}
      </div>
      <div className="mono-label mt-2">{label}</div>
    </div>
  );
}
