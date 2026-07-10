/**
 * Badge — Bugatti redesign.
 *
 * Transparent background + hairline border (or no border) + mono uppercase
 * with 2px tracking. The pill radius is the one Bugatti-permitted curve.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-mono uppercase text-[11px] tracking-[0.18em] transition-colors border",
  {
    variants: {
      variant: {
        default:  "border-[color:var(--hairline)] bg-transparent text-[color:var(--muted)]",
        live:     "border-[color:var(--ink)] bg-transparent text-[color:var(--ink)]",
        positive: "border-[color:rgba(95,166,87,0.4)] bg-transparent text-[color:var(--success)]",
        negative: "border-[color:var(--hairline)] bg-transparent text-[color:var(--muted)]",
        info:     "border-[color:rgba(195,217,243,0.4)] bg-transparent text-[color:var(--link)]",
        muted:    "border-[color:var(--hairline)] bg-transparent text-[color:var(--muted)]",
        outline:  "border-[color:var(--hairline-strong)] bg-transparent text-[color:var(--body)]",
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
