/**
 * Card — shadcn-style surface primitive, theme-aware via design tokens.
 *
 * Cinematic overhaul (2026-05+): added `surface` variants for the
 * motorsport visual language while keeping the legacy `flat` default
 * 100% backwards compatible.  `paddock` resolves --team-color from
 * either an inline style prop or a [data-team] ancestor.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const cardVariants = cva(
  "rounded-[12px] text-[color:var(--text-primary)] transition-[border-color,box-shadow,transform] duration-200",
  {
    variants: {
      surface: {
        flat: "border border-[color:var(--border)] bg-[color:var(--surface)]",
        glow: "card-glow",
        hud: "hud-frame",
        paddock: "card-paddock",
      },
      interactive: {
        true: "cursor-pointer",
        false: "",
      },
    },
    defaultVariants: { surface: "flat", interactive: false },
  },
);

interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  teamColor?: string;
  team?: string;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, surface, interactive, teamColor, team, style, ...props }, ref) => {
    const inlineStyle: React.CSSProperties = teamColor
      ? ({ ...style, ["--team-color" as string]: teamColor } as React.CSSProperties)
      : style ?? {};
    return (
      <div
        ref={ref}
        data-team={team}
        className={cn(cardVariants({ surface, interactive }), className)}
        style={inlineStyle}
        {...props}
      />
    );
  },
);
Card.displayName = "Card";

export const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1.5 p-6", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-lg font-semibold leading-tight tracking-tight", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-[color:var(--text-muted)]", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

export const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

export const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  ),
);
CardFooter.displayName = "CardFooter";
