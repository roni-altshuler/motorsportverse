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
      className={cn(
        "relative z-10 w-full",
        className,
      )}
      style={
        {
          "--border-size": `${borderSize}px`,
          "--border-radius": `${borderRadius}px`,
          "--neon-first-color": neonColors.firstColor,
          "--neon-second-color": neonColors.secondColor,
        } as CSSProperties
      }
    >
      <div
        className="relative h-full w-full overflow-hidden p-[var(--border-size)] rounded-[var(--border-radius)]"
        style={{
          background:
            "linear-gradient(0deg, var(--neon-first-color), var(--neon-second-color))",
          backgroundSize: "200% 200%",
          animation: "neon-pulse 6s ease infinite",
        }}
      >
        <div
          className="relative z-10 h-full w-full bg-[var(--surface-card)] rounded-[calc(var(--border-radius)-1px)]"
        >
          {children}
        </div>
      </div>
      <div
        className="pointer-events-none absolute -inset-2 -z-10 rounded-[var(--border-radius)] opacity-60 blur-2xl"
        style={{
          background:
            "linear-gradient(0deg, var(--neon-first-color), var(--neon-second-color))",
        }}
      />
    </div>
  );
}
