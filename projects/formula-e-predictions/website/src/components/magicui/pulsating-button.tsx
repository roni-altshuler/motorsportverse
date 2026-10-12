"use client";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/components/ui/cn";
interface PulsatingButtonProps extends ComponentPropsWithoutRef<"button"> {
  pulseColor?: string;
  duration?: string;
}
/** Static status button. The label conveys state without an expanding ring. */
export function PulsatingButton({
  className,
  children,
  pulseColor = "#E10600",
  style,
  ...props
}: PulsatingButtonProps) {
  delete props.duration;
  return (
    <button
      {...props}
      className={cn(
        "relative inline-flex cursor-pointer items-center justify-center rounded-full px-3 py-1 text-[11px] font-mono uppercase tracking-[0.18em] text-white transition-colors hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ink)]",
        className,
      )}
      style={{ backgroundColor: pulseColor, ...style }}
    >
      {children}
    </button>
  );
}
