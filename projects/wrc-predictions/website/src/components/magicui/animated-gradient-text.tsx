"use client";

import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/components/ui/cn";

interface AnimatedGradientTextProps extends ComponentPropsWithoutRef<"span"> {
  /** Gradient duration in seconds. Default 8. */
  speed?: number;
  /** From color. */
  colorFrom?: string;
  /** To color. */
  colorTo?: string;
}

/**
 * Animated linear gradient text. Uses background-clip:text and animates
 * the background position. Reduced-motion stops the animation but keeps
 * the gradient visible (degrades to a static colored fill).
 */
export function AnimatedGradientText({
  speed = 8,
  colorFrom = "#E10600",
  colorTo = "#FFD166",
  className,
  children,
  style,
  ...props
}: AnimatedGradientTextProps) {
  return (
    <span
      {...props}
      className={cn(
        "inline-block bg-clip-text text-transparent animate-gradient",
        className,
      )}
      style={{
        backgroundImage: `linear-gradient(90deg, ${colorFrom}, ${colorTo}, ${colorFrom})`,
        backgroundSize: "200% 100%",
        animationDuration: `${speed}s`,
        ...style,
      }}
    >
      {children}
    </span>
  );
}
