"use client";

import { motion, type MotionStyle, type Transition } from "framer-motion";

import { cn } from "@/components/ui/cn";

interface BorderBeamProps {
  /** Beam thickness in px. Default 1. */
  size?: number;
  /** Animation duration in seconds. Default 6. */
  duration?: number;
  /** Animation delay in seconds. */
  delay?: number;
  /** Conic gradient stops (CSS gradient string). Default = F1 red + blue. */
  colorFrom?: string;
  colorTo?: string;
  className?: string;
  /** Reverse the spin direction. */
  reverse?: boolean;
  /** Where the beam starts (0–100). */
  initialOffset?: number;
  /** Beam border radius in px. Default 0 (matches the Bugatti card radius). */
  borderRadius?: number;
  /** Override transition (e.g. for reduced motion). */
  transition?: Transition;
}

export function BorderBeam({
  className,
  size = 1,
  duration = 6,
  delay = 0,
  colorFrom = "#E10600",
  colorTo = "#3671C6",
  transition,
  reverse = false,
  initialOffset = 0,
  borderRadius = 0,
}: BorderBeamProps) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 [container-type:size]",
        className,
      )}
      style={{ borderRadius }}
      aria-hidden
    >
      <div
        className={cn(
          "absolute inset-0 overflow-hidden",
          "[mask:linear-gradient(transparent,transparent),linear-gradient(black,black)]",
          "[mask-clip:padding-box,border-box] [mask-composite:intersect]",
        )}
        style={{
          borderRadius,
          padding: `${size}px`,
        }}
      >
        <motion.div
          className={cn("absolute aspect-square", "bg-gradient-to-l")}
          style={
            {
              width: "calc(100cqh * 5)",
              offsetPath: `rect(0 auto auto 0 round ${borderRadius}px)`,
              "--color-from": colorFrom,
              "--color-to": colorTo,
              background: `linear-gradient(to left, ${colorFrom}, ${colorTo}, transparent)`,
            } as MotionStyle
          }
          initial={{ offsetDistance: `${initialOffset}%` }}
          animate={{
            offsetDistance: reverse
              ? [`${100 - initialOffset}%`, `${-initialOffset}%`]
              : [`${initialOffset}%`, `${100 + initialOffset}%`],
          }}
          transition={{
            repeat: Infinity,
            ease: "linear",
            duration,
            delay: -delay,
            ...transition,
          }}
        />
      </div>
    </div>
  );
}
