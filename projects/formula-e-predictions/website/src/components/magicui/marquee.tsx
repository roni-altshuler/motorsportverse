"use client";

import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/components/ui/cn";

interface MarqueeProps extends ComponentPropsWithoutRef<"div"> {
  /** Pause animation on hover. */
  pauseOnHover?: boolean;
  /** Vertical scroll direction (default false = horizontal). */
  vertical?: boolean;
  /** Number of copies of the children (so the loop appears seamless). */
  repeat?: number;
  /** Reverse scroll direction. */
  reverse?: boolean;
}

/**
 * Infinite seamless marquee using a duplicated child and a CSS keyframe.
 * The keyframe `marquee` (and `marquee-vertical`) is injected via the
 * tailwind `@theme inline` block in globals.css.
 *
 * Pure CSS — no JS animation loop, no measurement. Respects
 * `prefers-reduced-motion` via the global media-query in globals.css.
 */
export function Marquee({
  className,
  reverse,
  pauseOnHover = false,
  children,
  vertical = false,
  repeat = 4,
  ...props
}: MarqueeProps) {
  return (
    <div
      {...props}
      className={cn(
        "group flex overflow-hidden p-2 [--duration:40s] [--gap:1rem] [gap:var(--gap)]",
        vertical ? "flex-col" : "flex-row",
        className,
      )}
    >
      {Array.from({ length: repeat }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "flex shrink-0 justify-around [gap:var(--gap)]",
            vertical
              ? "animate-marquee-vertical flex-col"
              : "animate-marquee flex-row",
            pauseOnHover && "group-hover:[animation-play-state:paused]",
            reverse && "[animation-direction:reverse]",
          )}
        >
          {children}
        </div>
      ))}
    </div>
  );
}
