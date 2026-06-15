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
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">Documentation</h1>
      <p className="mt-3 max-w-2xl text-[var(--ink-muted)]">
        Everything you need to understand the ecosystem and ship a new motorsport
        project on top of the shared infrastructure.
      </p>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <a
            key={s.title}
            href={s.href}
            className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6 transition-colors hover:border-[var(--accent)]"
          >
            <h2 className="text-base font-semibold text-[var(--ink)]">{s.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-[var(--ink-muted)]">{s.body}</p>
          </a>
        ))}
      </div>
    </div>
  );
}
