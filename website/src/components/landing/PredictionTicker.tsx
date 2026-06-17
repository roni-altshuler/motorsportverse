"use client";

/**
 * PredictionTicker — a live-feed style strip of model outputs.
 *
 * No real prediction feed ships under public/data yet, so the parent
 * synthesizes plausible, deterministic rows from the registry (sport +
 * accent + maturity). This is presentation-only; rows are clearly framed as
 * model estimates, consistent with the site's "not betting advice" footer.
 */

import { Marquee } from "@/components/magicui/marquee";

export interface TickerRow {
  key: string;
  sport: string;
  accent: string;
  label: string; // e.g. "Verstappen"
  metric: string; // e.g. "WIN 41%"
  delta: number; // +/- trend
  live: boolean;
}

export function PredictionTicker({ rows }: { rows: TickerRow[] }) {
  return (
    <div className="relative border-y border-[var(--line)] bg-[var(--canvas-deep)]/60 py-3">
      <Marquee pauseOnHover className="[--duration:46s] [--gap:0.9rem]">
        {rows.map((r) => (
          <div
            key={r.key}
            className="flex items-center gap-3 rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface)]/70 px-4 py-2 backdrop-blur"
          >
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: r.accent }}
              aria-hidden
            />
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--ink-dim)]">
              {r.sport}
            </span>
            <span className="text-sm font-medium text-[var(--ink)]">{r.label}</span>
            <span className="text-xs font-semibold text-[var(--ink-muted)]">{r.metric}</span>
            <span
              className="text-xs font-mono tabular-nums"
              style={{ color: r.delta >= 0 ? "var(--maturity-production)" : "var(--accent-text)" }}
            >
              {r.delta >= 0 ? "▲" : "▼"} {Math.abs(r.delta).toFixed(1)}
            </span>
            {r.live && (
              <span className="mono-label flex items-center gap-1.5 text-[var(--maturity-production)]">
                <span className="live-dot !h-1.5 !w-1.5" />
                live
              </span>
            )}
          </div>
        ))}
      </Marquee>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-28 bg-gradient-to-r from-[var(--canvas)] to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-28 bg-gradient-to-l from-[var(--canvas)] to-transparent" />
    </div>
  );
}
