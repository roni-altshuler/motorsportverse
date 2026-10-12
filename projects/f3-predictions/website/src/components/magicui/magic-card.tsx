"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
interface MagicCardProps {
  children?: ReactNode;
  className?: string;
  gradientSize?: number;
  gradientColor?: string;
  gradientOpacity?: number;
  gradientFrom?: string;
  gradientTo?: string;
}
/** Static card surface. Legacy gradient props remain accepted for callers. */
export function MagicCard({ children, className }: MagicCardProps) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-[var(--radius-card,4px)] border border-[var(--hairline)] bg-[var(--surface-card)] transition-colors hover:border-[var(--hairline-strong)] focus-within:border-[var(--hairline-strong)]",
        className,
      )}
    >
      <div className="relative h-full w-full">{children}</div>
    </div>
  );
}
