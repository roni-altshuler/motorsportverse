import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-[var(--hairline)] bg-[var(--surface)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 text-sm text-[var(--ink-dim)] sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-semibold text-[var(--ink-muted)]">MotorsportVerse</span> — an
          open-source motorsport AI ecosystem.
        </p>
        <div className="flex gap-6">
          <Link href="/projects" className="hover:text-[var(--ink)]">
            Projects
          </Link>
          <Link href="/docs" className="hover:text-[var(--ink)]">
            Docs
          </Link>
          <a href="https://github.com/motorsportverse" className="hover:text-[var(--ink)]">
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
