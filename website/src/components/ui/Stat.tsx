/**
 * Stat — telemetry-style numeric display.
 *
 * Pairs a tabular-figures monospace value with an uppercase tracked label.
 * The intended use is dashboards: lap deltas, win-probabilities, pit-loss
 * seconds, gap-to-leader, etc.  Use the `tone` prop to colour positive
 * deltas (green) or negative deltas (red).
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const statVariants = cva(
  "flex flex-col gap-1 rounded-[8px] border border-[color:var(--border)] bg-[color:var(--surface-elevated)] p-3",
  {
    variants: {
      tone: {
        default: "",
        positive: "border-[color:color-mix(in_srgb,var(--accent-positive)_28%,transparent)]",
        negative: "border-[color:color-mix(in_srgb,var(--accent-negative)_28%,transparent)]",
        live: "border-[color:var(--border-accent)]",
      },
      size: {
        sm: "p-2.5",
        md: "p-3",
        lg: "p-4",
      },
    },
    defaultVariants: {
      tone: "default",
      size: "md",
    },
  },
);

const valueColor = (tone: StatProps["tone"]) => {
  switch (tone) {
    case "positive":
      return "text-[color:var(--accent-positive)]";
    case "negative":
      return "text-[color:var(--accent-negative)]";
    case "live":
      return "text-[color:var(--accent-live)]";
    default:
      return "text-[color:var(--text-primary)]";
  }
};

export interface StatProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "value">,
    VariantProps<typeof statVariants> {
  label: React.ReactNode;
  value: React.ReactNode;
  hint?: React.ReactNode;
}

export function Stat({ label, value, hint, tone, size, className, ...props }: StatProps) {
  return (
    <div className={cn(statVariants({ tone, size }), className)} {...props}>
      <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
        {label}
      </div>
      <div
        className={cn(
          "font-mono font-tabular text-2xl font-extrabold leading-none tracking-tight",
          valueColor(tone),
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="text-[11px] text-[color:var(--text-muted)]">{hint}</div>
      ) : null}
    </div>
  );
}
