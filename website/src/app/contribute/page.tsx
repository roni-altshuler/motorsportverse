import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contribute — MotorsportVerse",
  description: "How to add a sport, improve a model, or build a project in the MotorsportVerse ecosystem.",
};

const STEPS = [
  {
    n: "01",
    title: "Register your project",
    body: "Add a JSON entry under registry/projects/ describing the sport, category, and maturity. Run scripts/build_registry.py to validate it.",
  },
  {
    n: "02",
    title: "Scaffold from the template",
    body: "Run scripts/new_project.py <sport>-predictions to generate a project folder wired to motorsport-core and motorsport-data.",
  },
  {
    n: "03",
    title: "Implement a DataSource",
    body: "Tell the ecosystem where your data comes from by subclassing DataSource (calendar, grid, results).",
  },
  {
    n: "04",
    title: "Implement a Predictor",
    body: "Supply features and a fit procedure. Reuse calibration, the model registry, drift detection, and forward-eval unchanged.",
  },
  {
    n: "05",
    title: "Ship a website",
    body: "Copy the design system, point the data layer at your project's JSON output, and deploy the static export.",
  },
];

export default function ContributePage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">Contribute</h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        MotorsportVerse grows one sport at a time. The shared core does the heavy
        lifting — you bring the data and the domain knowledge.
      </p>
      <ol className="mt-10 space-y-5">
        {STEPS.map((s) => (
          <li
            key={s.n}
            className="flex gap-4 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5"
          >
            <span className="text-sm font-bold" style={{ color: "var(--accent)" }}>
              {s.n}
            </span>
            <div>
              <h2 className="text-base font-semibold text-[var(--ink)]">{s.title}</h2>
              <p className="mt-1 text-sm leading-relaxed text-[var(--ink-muted)]">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
