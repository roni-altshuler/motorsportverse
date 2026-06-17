import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Docs — MotorsportVerse",
  description: "Documentation for the MotorsportVerse ecosystem, packages, and contribution flow.",
};

const SECTIONS = [
  {
    title: "Architecture",
    body: "How motorsport-core and motorsport-data layer beneath each sport project.",
    href: "https://github.com/motorsportverse/motorsportverse/blob/main/docs/architecture.md",
  },
  {
    title: "Adding a sport",
    body: "Scaffold a new prediction project from the template and wire it to the shared core.",
    href: "https://github.com/motorsportverse/motorsportverse/blob/main/docs/adding-a-sport.md",
  },
  {
    title: "motorsport-core API",
    body: "Calibration, registry, drift, promotion, Elo, and evaluation reference.",
    href: "https://github.com/motorsportverse/motorsportverse/blob/main/docs/core-api.md",
  },
  {
    title: "Data schema",
    body: "The canonical Season / Round / Competitor / Result / Prediction models.",
    href: "https://github.com/motorsportverse/motorsportverse/blob/main/docs/data-schema.md",
  },
  {
    title: "Design system",
    body: "Tokens, components, and the shared visual identity.",
    href: "https://github.com/motorsportverse/motorsportverse/blob/main/docs/design-system.md",
  },
];

export default function DocsPage() {
  return (
    <div className="shell section">
      <p className="eyebrow eyebrow-accent eyebrow-tick">Documentation</p>
      <h1 className="display mt-3 text-5xl">Build on the core</h1>
      <p className="lead mt-4 max-w-2xl">
        Everything you need to understand the ecosystem and ship a new motorsport project on top of
        the shared infrastructure.
      </p>
      <div className="mt-12 grid gap-5 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <a key={s.title} href={s.href} className="card-surface hover-lift group p-6">
            <h2 className="font-display text-lg font-semibold text-[var(--ink)]">{s.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">{s.body}</p>
            <span className="mt-4 inline-block text-sm font-medium text-[var(--accent-bright)] transition-transform group-hover:translate-x-1">
              Read →
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
