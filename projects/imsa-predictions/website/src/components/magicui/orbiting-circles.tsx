"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
interface OrbitingCirclesProps {
  className?: string;
  children?: ReactNode;
  reverse?: boolean;
  duration?: number;
  delay?: number;
  radius?: number;
  pathColor?: string | null;
  pathWidth?: number;
}
/** Static radial layout. Legacy timing props determine a fixed badge position. */
export function OrbitingCircles({
  className,
  children,
  reverse = false,
  duration = 20,
  delay = 0,
  radius = 160,
  pathColor = "rgba(255, 255, 255, 0.10)",
  pathWidth = 1,
}: OrbitingCirclesProps) {
  const angle = duration > 0 ? (delay / duration) * 360 * (reverse ? -1 : 1) : 0;
  return (
    <>
      {pathColor !== null ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="pointer-events-none absolute inset-0 size-full"
          aria-hidden
        >
          <circle
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
        className={cn("absolute left-1/2 top-1/2 flex items-center justify-center", className)}
        style={{
          transform: `translate(-50%, -50%) rotate(${angle}deg) translateX(${radius}px) rotate(${-angle}deg)`,
        }}
      >
        {children}
      </div>
    </>
  );
}
