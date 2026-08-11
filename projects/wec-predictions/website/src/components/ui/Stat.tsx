/**
 * Stat — Bugatti redesign.
 *
 * Spec-cell pattern: transparent + hairline divider, label in eyebrow
 * (mono uppercase), value in title-md (Saira Display) + tabular figures.
 * Tone variants collapse to hairline borders — chromatic distinction comes
 * from semantic tokens (success, link, etc.) on the value text only.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const statVariants = cva(
  "flex flex-col gap-2 border border-[color:var(--hairline)] bg-transparent rounded-none",
  {
    variants: {
      tone: {
        default: "",
        positive: "",
        negative: "",
        live: "",
      },
      size: {
        sm: "p-3",
        md: "p-4",
        lg: "p-6",
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
      return "text-[color:var(--success)]";
    case "negative":
      return "text-[color:var(--muted)]";
    case "live":
      return "text-[color:var(--ink)]";
    default:
      return "text-[color:var(--ink)]";
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
      <div className="eyebrow">{label}</div>
      <div
        className={cn(
          "title-md font-tabular leading-none",
          valueColor(tone),
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="body-sm text-[color:var(--muted)]">{hint}</div>
      ) : null}
    </div>
  );
}
