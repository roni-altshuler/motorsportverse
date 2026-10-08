"use client";

/**
 * Global error boundary — the root layout itself threw.
 *
 * This is the only component that must render its own <html> and <body>: at
 * this point the root layout is gone, so there is no shell to inherit. Styling
 * is inline for the same reason — the stylesheet may be exactly what failed.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" data-theme="dark" style={{ colorScheme: "dark" }}>
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          background: "var(--canvas, #060910)",
          color: "var(--ink, #f4f7fb)",
          fontFamily: "var(--font-sans, ui-sans-serif, system-ui, sans-serif)",
          textAlign: "center",
          padding: "2rem",
        }}
      >
        <h1
          style={{
            fontSize: "1.25rem",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          MotorsportVerse failed to load
        </h1>
        <p
          style={{
            color: "var(--ink-muted, #aeb8c6)",
            maxWidth: "34rem",
            lineHeight: 1.6,
          }}
        >
          The application shell itself threw. Reloading is the only useful
          action from here.
        </p>
        {error.digest ? (
          <p
            style={{
              color: "var(--ink-dim, #8994a4)",
              fontSize: "0.75rem",
              fontFamily: "ui-monospace, monospace",
            }}
          >
            digest {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: "0.5rem",
            padding: "0.6rem 1.2rem",
            border: "1px solid var(--hairline-strong, #2c3848)",
            borderRadius: "999px",
            minHeight: "44px",
            background: "transparent",
            color: "var(--ink, #f4f7fb)",
            cursor: "pointer",
            fontFamily: "inherit",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
