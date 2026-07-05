"use client";

/**
 * KeyFactorBars — compact horizontal factor-weight bars for one driver.
 *
 * Renders the plain-language "why" behind a predicted result: factor label,
 * relative-weight bar, and direction. Per the Bugatti palette discipline,
 * advantage/neutral factors render in ink/muted; F1 red is reserved for
 * risk factors only.
 */
import type { KeyFactor } from "@/types";
import { cn } from "@/components/ui/cn";

interface KeyFactorBarsProps {
  factors: KeyFactor[];
  /** Compact mode tightens spacing for inline (row-expansion) use. */
  compact?: boolean;
  className?: string;
}

function factorTone(direction: KeyFactor["direction"]): {
  bar: string;
  label: string;
  tag: string | null;
} {
  if (direction === "risk") {
    return {
      bar: "var(--accent-f1-red)",
      label: "var(--accent-f1-red-bright)",
      tag: "Risk",
    };
  }
  if (direction === "advantage") {
    return { bar: "var(--ink)", label: "var(--body-strong)", tag: null };
  }
  return { bar: "var(--muted)", label: "var(--muted)", tag: null };
}

export default function KeyFactorBars({ factors, compact, className }: KeyFactorBarsProps) {
  if (!factors || factors.length === 0) return null;
  return (
    <ul className={cn(compact ? "space-y-2" : "space-y-3", className)}>
      {factors.map((factor) => {
        const tone = factorTone(factor.direction);
        const weightPct = Math.round(Math.min(Math.max(factor.weight, 0), 1) * 100);
        // Keep a small visible floor so a near-zero (but present) factor
        // reads as "minor", not as a rendering bug.
        const widthPct = factor.weight > 0 ? Math.max(weightPct, 3) : 0;
        return (
          <li key={factor.factor}>
            <div className="flex items-baseline justify-between gap-2 mb-1">
              <span
                className={cn(
                  "font-mono uppercase tracking-[0.14em]",
                  compact ? "text-[10px]" : "text-[11px]",
                )}
                style={{ color: tone.label }}
              >
                {factor.factor}
              </span>
              {tone.tag && (
                <span
                  className="font-mono uppercase tracking-[0.14em] text-[9px] px-1.5 py-px"
                  style={{
                    color: "var(--accent-f1-red-bright)",
                    border: "1px solid color-mix(in srgb, var(--accent-f1-red) 45%, transparent)",
                    background: "var(--accent-f1-red-soft)",
                  }}
                >
                  {tone.tag}
                </span>
              )}
            </div>
            <div
              className={cn("w-full", compact ? "h-[3px]" : "h-1")}
              style={{ background: "var(--hairline)" }}
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={weightPct}
              aria-label={`${factor.factor} — relative emphasis ${weightPct}%${
                factor.direction === "risk" ? ", working against this driver" : ""
              }`}
            >
              <div
                className="h-full transition-[width] duration-500 ease-out motion-reduce:transition-none"
                style={{ width: `${widthPct}%`, background: tone.bar }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
