/**
 * StatusBanner — the page says which state it is in, rather than degrading quietly.
 *
 * Four states, and each one changes how the numbers below should be read:
 *
 * - `backtest`  — a reconstruction. Nobody read these numbers before the race.
 *   Always `--warning`, always the word "backtest", per DESIGN.md §8.3.
 * - `uncalibrated` — the calibration gate is closed, so the probabilities are
 *   raw model output and are not confidence levels.
 * - `stale` — the data is older than the last completed round.
 * - `archived` — a finished season, kept for reference.
 * - `fantasy` — a simulated, fan-made league. Not a prediction of anything real.
 *
 * The banner is not dismissible. A caveat a reader can close is a caveat that
 * stops applying the moment it is inconvenient.
 */
import * as React from "react";
import { cn } from "./cn";

export type StatusKind =
  | "backtest"
  | "uncalibrated"
  | "stale"
  | "archived"
  | "fantasy"
  | "info";

const TONE: Record<StatusKind, string> = {
  // Backtest and uncalibrated both mean "read this differently", which is what
  // --warning is for. Neither is an error, so neither gets the negative accent.
  backtest: "border-[color:var(--warning)] text-[color:var(--warning)]",
  uncalibrated: "border-[color:var(--warning)] text-[color:var(--warning)]",
  fantasy: "border-[color:var(--warning)] text-[color:var(--warning)]",
  stale: "border-[color:var(--hairline-strong)] text-[color:var(--muted)]",
  archived: "border-[color:var(--hairline-strong)] text-[color:var(--muted)]",
  info: "border-[color:var(--hairline)] text-[color:var(--muted)]",
};

const LABEL: Record<StatusKind, string> = {
  backtest: "Backtest",
  uncalibrated: "Uncalibrated",
  stale: "Stale",
  archived: "Archived",
  fantasy: "Simulated",
  info: "Note",
};

export function StatusBanner({
  kind,
  children,
  className,
}: {
  kind: StatusKind;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      data-testid="status-banner"
      data-kind={kind}
      role="note"
      className={cn(
        "flex flex-wrap items-baseline gap-x-3 gap-y-1 border-l-2 bg-[color:var(--surface-soft)] px-4 py-3",
        TONE[kind],
        className,
      )}
    >
      <span className="eyebrow shrink-0">{LABEL[kind]}</span>
      <span className="body-sm text-[color:var(--body)]">{children}</span>
    </div>
  );
}
