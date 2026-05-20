/**
 * Badge — small pill for status / category labels.  Variants map to the
 * semantic accents defined in tokens.css so the same Badge automatically
 * recolours under light/dark theme swap.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.08em] transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-[color:var(--border)] bg-[color:var(--surface-elevated)] text-[color:var(--text-primary)]",
        live:
          "border-[color:var(--border-accent)] bg-[color:color-mix(in_srgb,var(--accent-live)_14%,transparent)] text-[color:var(--accent-live)]",
        positive:
          "border-[color:color-mix(in_srgb,var(--accent-positive)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-positive)_14%,transparent)] text-[color:var(--accent-positive)]",
        negative:
          "border-[color:color-mix(in_srgb,var(--accent-negative)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-negative)_14%,transparent)] text-[color:var(--accent-negative)]",
        info:
          "border-[color:color-mix(in_srgb,var(--accent-info)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--accent-info)_14%,transparent)] text-[color:var(--accent-info)]",
        muted:
          "border-transparent bg-[color:var(--surface-elevated)] text-[color:var(--text-muted)]",
        outline:
          "border-[color:var(--border-strong)] bg-transparent text-[color:var(--text-secondary)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
