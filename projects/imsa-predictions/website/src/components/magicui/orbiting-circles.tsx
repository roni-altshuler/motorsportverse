"use client";

import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/components/ui/cn";

interface OrbitingCirclesProps {
  className?: string;
  children?: ReactNode;
  reverse?: boolean;
  /** Animation duration in seconds. Default 20. */
  duration?: number;
  /** Delay in seconds before the orbit begins. */
  delay?: number;
  /** Orbit radius in px. Default 160. */
  radius?: number;
  /** Path stroke color (CSS color). Pass null to hide the path. */
  pathColor?: string | null;
  /** Path stroke width in px. Default 1. */
  pathWidth?: number;
}

/**
 * Single orbiting element wrapped in an SVG-stroked circular path.
 * Multiple instances can share a parent to compose a constellation.
 *
 * Children receive a translateX(radius) so they sit on the right edge of
 * the orbit; the rotation animation does the rest.
 */
export function OrbitingCircles({
  className,
  children,
  reverse,
  duration = 20,
  delay = 0,
  radius = 160,
  pathColor = "rgba(255, 255, 255, 0.10)",
  pathWidth = 1,
}: OrbitingCirclesProps) {
  return (
    <>
      {pathColor !== null ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          version="1.1"
          className="pointer-events-none absolute inset-0 size-full"
          aria-hidden
        >
          <circle
            className="stroke-1"
            cx="50%"
            cy="50%"
            r={radius}
            fill="none"
            stroke={pathColor}
            strokeWidth={pathWidth}
          />
        </svg>
      ) : null}

      <div
        style={
          {
            "--duration": `${duration}`,
            "--radius": radius,
            "--delay": `-${delay}s`,
          } as CSSProperties
        }
        className={cn(
          "absolute left-1/2 top-1/2 flex h-full w-full transform-gpu items-center justify-center [animation-duration:calc(var(--duration)*1s)] [animation-delay:var(--delay)] animate-orbit",
          { "[animation-direction:reverse]": reverse },
          className,
        )}
      >
        <div
          className="flex items-center justify-center"
          style={{ transform: `translateX(${radius}px)` }}
        >
          {children}
        </div>
      </div>
    </>
  );
}
