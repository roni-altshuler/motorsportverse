export function Footer() {
  return (
    <footer className="border-t border-[var(--hairline)] bg-[var(--surface)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-10 text-sm text-[var(--ink-dim)] sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-semibold text-[var(--ink-muted)]">RaceIQ F2</span> — a
          MotorsportVerse project. Forecasts are model estimates, not betting advice.
        </p>
        <a href="https://motorsportverse.org/projects/f2-predictions" className="hover:text-[var(--ink)]">
          About this project →
        </a>
      </div>
    </footer>
  );
}
