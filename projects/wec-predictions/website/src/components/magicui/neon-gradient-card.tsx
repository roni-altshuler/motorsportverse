"use client";

import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/components/ui/cn";

interface NeonGradientCardProps {
  borderSize?: number;
  borderRadius?: number;
  neonColors?: {
    firstColor: string;
    secondColor: string;
  };
  className?: string;
  children?: ReactNode;
}

/**
 * Card with a soft glowing gradient border. Used ONCE per page max — the
 * live race card during a Grand Prix weekend.
 *
 * The neon "pulse" is a conic gradient rotated via `transform`, which the
 * compositor handles on the GPU — no repaints, no layout, no
 * background-position thrash like the previous implementation.
 */
export function NeonGradientCard({
  borderSize = 2,
  borderRadius = 4,
  neonColors = { firstColor: "#E10600", secondColor: "#3671C6" },
  className,
  children,
}: NeonGradientCardProps) {
  return (
    <div
      className={cn("relative z-10 w-full", className)}
      style={
        {
          "--border-size": `${borderSize}px`,
          "--border-radius": `${borderRadius}px`,
          "--neon-first-color": neonColors.firstColor,
          "--neon-second-color": neonColors.secondColor,
        } as CSSProperties
      }
    >
      <div className="relative h-full w-full overflow-hidden p-[var(--border-size)] rounded-[var(--border-radius)]">
        {/* Rotating conic-gradient backdrop. Sized larger than the parent +
         * centred so corners stay filled when the conic sweeps past 90/180/270. */}
        <div
          aria-hidden
          className="absolute left-1/2 top-1/2 aspect-square w-[180%] -translate-x-1/2 -translate-y-1/2 animate-neon-spin"
          style={{
            background:
              "conic-gradient(from 0deg, var(--neon-first-color), var(--neon-second-color), var(--neon-first-color))",
          }}
        />
        <div className="relative z-10 h-full w-full bg-[var(--surface-card)] rounded-[calc(var(--border-radius)-1px)]">
          {children}
        </div>
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-2 -z-10 rounded-[var(--border-radius)] opacity-60 blur-2xl"
        style={{
          background:
            "linear-gradient(0deg, var(--neon-first-color), var(--neon-second-color))",
        }}
      />
    </div>
  );
}
