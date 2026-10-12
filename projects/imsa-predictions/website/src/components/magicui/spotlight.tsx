"use client";
import type { ReactNode } from "react";
import { cn } from "@/components/ui/cn";
interface SpotlightProps {
  children?: ReactNode;
  className?: string;
  size?: number;
  color?: string;
}
/** Solid surface with ordinary hover feedback; no cursor-following backdrop. */
export function Spotlight({ children, className }: SpotlightProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden transition-colors hover:bg-[var(--surface-soft)] focus-within:bg-[var(--surface-soft)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
