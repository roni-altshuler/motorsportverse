"use client";

import { useEffect } from "react";

/**
 * Route error boundary.
 *
 * Renders when a segment under this layout throws. It says plainly that the
 * page failed rather than showing a half-built board — a standings table
 * missing half its rows because something threw is worse than no table, since
 * a reader cannot tell the difference between "broken" and "these are the
 * standings".
 *
 * `reset()` re-renders the segment. A static export has no server to retry
 * against, so the honest label is "try again", not "reload data".
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // The digest is the only handle on a minified production stack trace.
    console.error("[wec-predictions] route error", error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-2xl flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="eyebrow">Error</p>
      <h1 className="display-md">This page failed to render</h1>
      <p className="body-md text-[color:var(--muted)]">
        Something went wrong building this view. Nothing here is a partial
        result — the page stopped rather than showing an incomplete one.
      </p>
      {error.digest ? (
        <p className="font-mono text-[11px] text-[color:var(--muted)]">
          digest {error.digest}
        </p>
      ) : null}
      <button type="button" onClick={reset} className="btn-bugatti mt-2">
        Try again
      </button>
    </main>
  );
}
