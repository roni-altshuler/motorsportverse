import Link from "next/link";

const DISCLAIMER =
  "A fan-made fictional league. All characters, venues and results are simulated and original. Not affiliated with any film studio.";

export default function Footer() {
  return (
    <footer className="hairline-divider-top mt-16 bg-[color:var(--surface-soft)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <p className="wordmark">Chrome Valley</p>
            <p className="eyebrow mt-2">Racing League — a simulated story</p>
          </div>
          <nav aria-label="Footer" className="flex gap-6">
            <Link href="/" className="nav-link-text text-[color:var(--muted)] hover:text-[color:var(--ink)]">
              Race Day
            </Link>
            <Link href="/garage/" className="nav-link-text text-[color:var(--muted)] hover:text-[color:var(--ink)]">
              The Garage
            </Link>
            <Link href="/season/" className="nav-link-text text-[color:var(--muted)] hover:text-[color:var(--ink)]">
              The Season
            </Link>
          </nav>
        </div>
        <p className="body-sm max-w-3xl text-[color:var(--muted)]">{DISCLAIMER}</p>
        <p className="mono-label">
          Every result on this site comes out of a seeded simulator — regenerate the whole season
          with one command, get the same story every time.
        </p>
      </div>
    </footer>
  );
}
