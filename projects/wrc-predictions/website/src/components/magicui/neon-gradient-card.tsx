"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
interface NeonGradientCardProps {
  borderSize?: number;
  borderRadius?: number;
  neonColors?: { firstColor: string; secondColor: string };
  className?: string;
  children?: ReactNode;
}
/** Static accent border for a featured race; no rotating or glowing layers. */
export function NeonGradientCard({
  borderSize = 2,
  borderRadius = 4,
  neonColors = { firstColor: "#E10600", secondColor: "#3671C6" },
  className,
  children,
}: NeonGradientCardProps) {
  return (
    <div
      className={cn("relative w-full overflow-hidden bg-[var(--surface-card)]", className)}
      style={{
        borderWidth: borderSize,
        borderStyle: "solid",
        borderColor: neonColors.firstColor,
        borderRadius,
      }}
    >
      {children}
    </div>
  );
}
