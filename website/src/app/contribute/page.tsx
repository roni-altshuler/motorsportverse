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
    <div className="shell section max-w-3xl">
      <p className="eyebrow eyebrow-accent eyebrow-tick">Contribute</p>
      <h1 className="display mt-3 text-5xl">Add a sport</h1>
      <p className="lead mt-4">
        MotorsportVerse grows one sport at a time. The shared core does the heavy lifting — you
        bring the data and the domain knowledge.
      </p>
      <ol className="mt-12 space-y-4">
        {STEPS.map((s) => (
          <li key={s.n} className="card-surface hover-lift flex gap-5 p-6">
            <span className="font-display text-2xl font-bold text-[var(--accent-bright)]">{s.n}</span>
            <div>
              <h2 className="font-display text-lg font-semibold text-[var(--ink)]">{s.title}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--ink-muted)]">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
