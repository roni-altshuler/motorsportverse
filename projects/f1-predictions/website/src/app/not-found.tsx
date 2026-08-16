import Link from "next/link";

/**
 * 404 — a missing page names what is missing and offers the way back.
 *
 * These sites are static exports over a season that grows: a link to round 18
 * is a 404 in March and a real page in September. The copy therefore says the
 * round may not have run yet rather than implying the reader mistyped it.
 */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="eyebrow">404</p>
      <h1 className="display-md">Page not found</h1>
      <p className="body-md text-[color:var(--muted)]">
        This page does not exist on RaceIQ F1. If you followed a link to a
        specific round, that round may not have run yet — the season fills in as
        it goes.
      </p>
      <Link href="/" className="link-bugatti mt-2">
        Back to the season
      </Link>
    </main>
  );
}
