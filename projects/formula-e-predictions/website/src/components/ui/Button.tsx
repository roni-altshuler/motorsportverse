/**
 * Button — Bugatti redesign.
 *
 * The signature Bugatti button is transparent + 1px ink outline + pill, with
 * uppercase monospace label at 2.5px tracking. All non-primary variants
 * collapse to the same look; size variants other than `icon` route to the
 * standard 44px primary button. `buttonVariants` is preserved so callers like
 * `<Link className={buttonVariants(...)}>` keep working.
 */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./cn";

const BASE_BTN = [
  "inline-flex items-center justify-center gap-2 whitespace-nowrap",
  "rounded-full border border-[color:var(--ink)] bg-transparent",
  "font-mono uppercase",
  "transition-colors duration-200",
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--canvas)]",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "text-[color:var(--ink)] hover:bg-[color:var(--ink)] hover:text-[color:var(--canvas)]",
].join(" ");

const buttonVariants = cva(BASE_BTN, {
  variants: {
    variant: {
      primary: "",
      secondary: "",
      outline: "",
      ghost: "border-transparent hover:bg-transparent hover:text-[color:var(--ink)] hover:underline underline-offset-4",
      destructive: "",
      link: "border-transparent hover:bg-transparent hover:text-[color:var(--ink)] hover:underline underline-offset-4 px-0",
    },
    size: {
      sm: "h-9 px-5 text-[12px] tracking-[0.18em]",
      md: "h-11 px-8 text-[14px] tracking-[0.18em]",
      lg: "h-11 px-8 text-[14px] tracking-[0.18em]",
      icon: "h-10 w-10 p-0 rounded-full",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "md",
  },
});

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
