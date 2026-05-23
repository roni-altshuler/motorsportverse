/**
 * Card — Bugatti redesign.
 *
 * Surface variants collapse to two:
 *   - flat (default): surface-card + hairline border + 0 radius
 *   - photo: canvas background, used for full-bleed photo card layouts
 *
 * The `glow`/`hud`/`paddock` variants are kept in the variant enum (so call
 * sites compile) but route to the `flat` surface — the Bugatti aesthetic
 * has no glow, no HUD frame, no team-color gradient backdrop.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const cardVariants = cva(
  "rounded-none text-[color:var(--ink)] transition-colors duration-200",
  {
    variants: {
      surface: {
        flat:    "border border-[color:var(--hairline)] bg-[color:var(--surface-card)]",
        photo:   "border-none bg-[color:var(--canvas)]",
        glow:    "border border-[color:var(--hairline)] bg-[color:var(--surface-card)]",
        hud:     "border border-[color:var(--hairline)] bg-[color:var(--surface-card)]",
        paddock: "border border-[color:var(--hairline)] bg-[color:var(--surface-card)]",
      },
      interactive: {
        true: "cursor-pointer hover:border-[color:var(--hairline-strong)]",
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
    <div ref={ref} className={cn("flex flex-col gap-2 p-6", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("title-md", className)}
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
    className={cn("body-sm text-[color:var(--muted)]", className)}
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
