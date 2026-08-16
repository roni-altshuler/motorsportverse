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
    <html lang="en" data-theme="dark">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          background: "#000000",
          color: "#ffffff",
          fontFamily: "ui-monospace, monospace",
          textAlign: "center",
          padding: "2rem",
        }}
      >
        <h1 style={{ fontSize: "1.25rem", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          RaceIQ F3 failed to load
        </h1>
        <p style={{ color: "#999999", maxWidth: "34rem", lineHeight: 1.6 }}>
          The application shell itself threw. Reloading is the only useful
          action from here.
        </p>
        {error.digest ? (
          <p style={{ color: "#666666", fontSize: "0.75rem" }}>digest {error.digest}</p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: "0.5rem",
            padding: "0.6rem 1.2rem",
            border: "1px solid #3a3a3a",
            background: "transparent",
            color: "#ffffff",
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
