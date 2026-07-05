"use client";

import * as React from "react";

interface ErrorBoundaryProps {
  /** Rendered when the child tree throws during render. */
  fallback?: React.ReactNode;
  /** Optional context label included in console.error logs. */
  label?: string;
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  message?: string;
}

/**
 * Minimal error boundary so a single broken component doesn't unmount the
 * entire page. Use around any subtree that consumes external data and could
 * realistically throw on partial/null/stale shapes (e.g. WhoCanWinLanes,
 * chart components consuming round JSON).
 *
 * Class component because React still requires the lifecycle methods
 * (getDerivedStateFromError + componentDidCatch) — there is no hook equivalent.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error?.message };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    if (typeof window !== "undefined") {
      // Surface to the browser console for debugging; do not crash.
      console.error(
        `[ErrorBoundary${this.props.label ? ` · ${this.props.label}` : ""}]`,
        error,
        info?.componentStack,
      );
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div
          role="alert"
          className="p-6 border border-[color:var(--hairline)] rounded-[var(--radius-card)] bg-[color:var(--surface-card)] text-center"
        >
          <p className="eyebrow mb-2">Something went wrong</p>
          <p className="body-sm text-[color:var(--muted)]">
            This section couldn{"'"}t load. Refresh the page to try again.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
