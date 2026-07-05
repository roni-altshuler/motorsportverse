import Link from "next/link";

import { CommandPaletteHint } from "@/components/landing/CommandPaletteHint";
import { CoverageWall, type CoverageItem } from "@/components/landing/CoverageWall";
import { EcosystemDiagram } from "@/components/landing/EcosystemDiagram";
import { FeatureBento } from "@/components/landing/FeatureBento";
import { PredictionTicker } from "@/components/landing/PredictionTicker";
import { ProductFilm } from "@/components/landing/ProductFilm";
import { Reveal } from "@/components/landing/Reveal";
import { ShowcaseRail } from "@/components/landing/ShowcaseRail";
import { SeriesMarquee } from "@/components/SeriesMarquee";
import { VerseHero } from "@/components/hero/VerseHero";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { getProjects } from "@/lib/registry";
import { synthTickerRows } from "@/lib/ticker";

const maturityRank = (m: string) =>
  m === "production" ? 0 : m === "experimental" ? 1 : m === "in-development" ? 2 : 3;

export default function HomePage() {
  const projects = getProjects();

  const operational = projects
    .filter((p) => p.maturity === "production" || p.maturity === "experimental")
    .sort((a, b) => maturityRank(a.maturity) - maturityRank(b.maturity));
  const inDevelopment = projects.filter((p) => p.maturity === "in-development");
  const tickerRows = synthTickerRows(projects);

  // Registry-driven ecosystem numbers (computed once, at build time).
  const seriesCovered = projects.length;
  const liveProducts = operational.length;
  const coreModules = new Set(projects.flatMap((p) => p.uses_core ?? [])).size;
  const modelsShipping = projects.reduce((n, p) => n + (p.models?.length ?? 0), 0);

  const marqueeItems = projects.map((p) => ({
    key: p.slug,
    sport: p.sport,
    icon: p.icon,
    accent: p.accent,
    maturity: p.maturity,
  }));

  const wallItems: CoverageItem[] = projects
    .slice()
    .sort((a, b) => maturityRank(a.maturity) - maturityRank(b.maturity))
    .map((p) => ({
      slug: p.slug,
      sport: p.sport,
      icon: p.icon,
      accent: p.accent || "#e7102f",
      maturity: p.maturity,
      website: p.website || undefined,
    }));

  const diagramSports = projects
    .slice()
    .sort((a, b) => maturityRank(a.maturity) - maturityRank(b.maturity))
    .map((p) => ({ slug: p.slug, sport: p.sport, icon: p.icon, accent: p.accent || "#e7102f" }));

  const heroStats = [
    { value: String(seriesCovered), label: "Racing series" },
    { value: String(liveProducts), label: "Live products" },
    { value: String(inDevelopment.length), label: "In build" },
    { value: "2", label: "Shared packages" },
  ];

  return (
    <div>
      {/* ====================== HERO ====================== */}
      <VerseHero stats={heroStats} />

      {/* ====================== LIVE PREDICTION TICKER ====================== */}
      <PredictionTicker rows={tickerRows} />

      {/* ====================== PRODUCT FILM (how it works) ====================== */}
      <ProductFilm />

      {/* ====================== ECOSYSTEM IN NUMBERS (registry-driven) ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal className="card-premium grid grid-cols-2 gap-px overflow-hidden bg-[var(--line)] sm:grid-cols-4">
            <CredStat value={seriesCovered} label="Racing series covered" />
            <CredStat value={liveProducts} label="Live prediction products" />
            <CredStat value={coreModules} label="Shared core modules" />
            <CredStat value={modelsShipping} label="Prediction models shipping" />
          </Reveal>
        </div>
      </section>

      {/* ====================== SERIES MARQUEE ====================== */}
      <section className="pb-14">
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
              <h2 className="mt-3 text-[length:var(--text-4xl)]">
                {liveProducts} products, forecasting real seasons
              </h2>
            </div>
            <Link
              href="/projects"
              className="text-sm font-medium text-[var(--accent-text)] transition-colors hover:text-[var(--accent-bright)]"
            >
              View all {seriesCovered} →
            </Link>
          </Reveal>
          <ShowcaseRail projects={operational} />
        </div>
      </section>

      {/* ====================== SERIES COVERAGE WALL ====================== */}
      <section className="section pt-0">
        <div className="shell">
          <Reveal className="mb-10 max-w-2xl">
            <p className="eyebrow eyebrow-accent eyebrow-tick">Series coverage</p>
            <h2 className="mt-3 text-[length:var(--text-4xl)]">
              {seriesCovered} series. One playbook.
            </h2>
            <p className="lead mt-4">
              {liveProducts} products publish calibrated forecasts today. Every other series is
              already scaffolded on the same two seams — and inherits the shared core the day its
              data feed lands.
            </p>
          </Reveal>
          <CoverageWall items={wallItems} />
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
              <div className="relative flex flex-col items-center text-center">
                <p className="eyebrow eyebrow-accent eyebrow-tick">Open to contributors</p>
                <h2 className="mt-4 max-w-2xl text-[length:var(--text-4xl)] sm:text-5xl">
                  Bring your sport to the grid.
                </h2>
                <p className="lead mt-5 max-w-xl">
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
    <div className="bg-[var(--surface)] px-4 py-10 text-center sm:px-6">
      <div className="font-display text-4xl font-bold text-[var(--ink)]">
        <NumberTicker value={value} />
        {suffix}
      </div>
      <div className="mono-label mt-2">{label}</div>
    </div>
  );
}
