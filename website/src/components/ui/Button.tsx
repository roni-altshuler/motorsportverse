/**
 * Button — shadcn-style polymorphic-ready button with variant + size.
 *
 * The `primary` variant uses telemetry orange (`--accent-live`), the
 * brand-defining accent of the redesigned palette.  Other variants compose
 * the surface and text tokens directly so light/dark swap is automatic.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "rounded-[8px] text-sm font-semibold",
    "transition-[background-color,color,box-shadow,transform] duration-150",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-live)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--bg)]",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "active:scale-[0.99]",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-[color:var(--accent-live)] text-[color:var(--accent-live-fg)] hover:bg-[color:var(--accent-live-hover)] shadow-[var(--shadow-sm)]",
        secondary:
          "bg-[color:var(--surface-elevated)] text-[color:var(--text-primary)] border border-[color:var(--border)] hover:bg-[color:color-mix(in_srgb,var(--accent-live)_8%,var(--surface-elevated))]",
        outline:
          "bg-transparent text-[color:var(--text-primary)] border border-[color:var(--border-strong)] hover:bg-[color:var(--surface-elevated)]",
        ghost:
          "bg-transparent text-[color:var(--text-secondary)] hover:bg-[color:var(--surface-elevated)] hover:text-[color:var(--text-primary)]",
        destructive:
          "bg-[color:var(--accent-negative)] text-[color:var(--accent-negative-fg)] hover:bg-[color:color-mix(in_srgb,var(--accent-negative)_85%,white)]",
        link:
          "bg-transparent text-[color:var(--accent-live)] underline-offset-4 hover:underline px-0",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-11 px-6 text-base",
        icon: "h-9 w-9 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
