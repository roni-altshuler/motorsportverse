"use client";

import type { ComponentPropsWithoutRef, CSSProperties } from "react";

import { cn } from "@/components/ui/cn";

interface PulsatingButtonProps extends ComponentPropsWithoutRef<"button"> {
  pulseColor?: string;
  duration?: string;
}

/**
 * Button with a pulsating ring expanding outward. Used for the LIVE pill
 * during a race weekend.
 */
export function PulsatingButton({
  className,
  children,
  pulseColor = "#E10600",
  duration = "1.5s",
  style,
  ...props
}: PulsatingButtonProps) {
  return (
    <button
      {...props}
      className={cn(
        "relative inline-flex cursor-pointer items-center justify-center",
        "rounded-full text-white px-3 py-1 text-[11px] font-mono uppercase tracking-[0.18em]",
        "[background:var(--pulse-bg,#E10600)]",
        className,
      )}
      style={
        {
          "--pulse-color": pulseColor,
          "--pulse-bg": pulseColor,
          "--duration": duration,
          ...style,
        } as CSSProperties
      }
    >
      <span className="relative z-10">{children}</span>
      <span className="absolute left-1/2 top-1/2 size-full -translate-x-1/2 -translate-y-1/2 animate-pulse-ring rounded-full bg-[var(--pulse-color)] opacity-30" />
    </button>
  );
}
