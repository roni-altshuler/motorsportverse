"use client";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/components/ui/cn";
interface AnimatedGradientTextProps extends ComponentPropsWithoutRef<"span"> {
  speed?: number;
  colorFrom?: string;
  colorTo?: string;
}
/** Static accent text gradient; the historical export name is retained. */
export function AnimatedGradientText({
  colorFrom = "#E10600",
  colorTo = "#FFD166",
  className,
  children,
  style,
  ...props
}: AnimatedGradientTextProps) {
  delete props.speed;
  return (
    <span
      {...props}
      className={cn("inline-block bg-clip-text text-transparent", className)}
      style={{ backgroundImage: `linear-gradient(90deg, ${colorFrom}, ${colorTo})`, ...style }}
    >
      {children}
    </span>
  );
}
