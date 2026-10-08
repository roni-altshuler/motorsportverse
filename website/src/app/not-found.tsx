import Link from "next/link";

/**
 * 404 — a missing page names what is missing and offers the way back.
 *
 * The hub is a project directory and race centre; it does not own series rounds.
 */
export default function NotFound() {
  return (
    <section
      aria-label="Page not found"
      className="mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col items-center justify-center gap-5 px-6 py-16 text-center"
    >
      <p className="eyebrow">404</p>
      <h1 className="display">Page not found</h1>
      <p className="lead">
        This page is unavailable. Return to the race centre to explore the
        published calendar, forecasts and series dashboards.
      </p>
      <Link
        href="/"
        className="btn-ghost mt-2 inline-flex min-h-11 items-center justify-center px-5 py-2.5 text-sm font-medium"
      >
        Back to race centre
      </Link>
    </section>
  );
}
