"use client";

/**
 * AmbientToggle — the reader's dial for the SpeedField backdrop.
 *
 * Three segmented buttons (soft · vivid · off), mono caption type, aria-pressed
 * on the active one. Hit area is extended vertically with a pseudo-element so
 * the 28px control still meets a 44px tap target in the navbar. Tokens only.
 */
import { setAmbient, useAmbient, type Ambient } from "@/lib/ambient";

const OPTIONS: readonly Ambient[] = ["soft", "vivid", "off"];

export function AmbientToggle({
  label = "Backdrop",
  compact = false,
  className,
}: {
  label?: string;
  /** Hide the caption below md — used in the navbar where width is scarce. */
  compact?: boolean;
  className?: string;
}) {
  const ambient = useAmbient();
  return (
    <div className={`flex items-center gap-2 ${className ?? ""}`}>
      <span className={`mono-label ${compact ? "hidden md:inline" : ""}`}>{label}</span>
      <div
        role="group"
        aria-label={`${label} animation`}
        className="inline-flex items-center rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface-2)]/60 px-0.5"
      >
        {OPTIONS.map((value, i) => {
          const on = value === ambient;
          return (
            <span key={value} className="inline-flex items-center">
              {i > 0 && (
                <span aria-hidden className="select-none font-mono text-[10px] text-[var(--ink-dim)]">
                  ·
                </span>
              )}
              <button
                type="button"
                aria-pressed={on}
                onClick={() => setAmbient(value)}
                className={`relative h-7 min-w-[44px] rounded-[var(--radius-pill)] px-2 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors before:absolute before:inset-x-0 before:-inset-y-2 before:content-[''] ${
                  on
                    ? "bg-[var(--surface-3)] text-[var(--ink)]"
                    : "text-[var(--ink-dim)] hover:text-[var(--ink-muted)]"
                }`}
              >
                {value}
              </button>
            </span>
          );
        })}
      </div>
    </div>
  );
}
