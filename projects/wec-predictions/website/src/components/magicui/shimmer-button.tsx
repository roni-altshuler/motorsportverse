"use client";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/components/ui/cn";
interface ShimmerButtonProps extends ComponentPropsWithoutRef<"button"> {
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
}
/** Static CTA with focus, hover and press feedback; no animated background. */
export function ShimmerButton({
  borderRadius = "9999px",
  background = "rgba(225, 6, 0, 0.95)",
  className,
  children,
  style,
  ...props
}: ShimmerButtonProps) {
  delete props.shimmerColor;
  delete props.shimmerSize;
  delete props.shimmerDuration;
  return (
    <button
      {...props}
      style={{ background, borderRadius, ...style }}
      className={cn(
        "relative inline-flex cursor-pointer items-center justify-center whitespace-nowrap border border-white/10 px-6 py-3 text-white transition-colors hover:brightness-110 active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ink)]",
        className,
      )}
    >
      {children}
    </button>
  );
}
