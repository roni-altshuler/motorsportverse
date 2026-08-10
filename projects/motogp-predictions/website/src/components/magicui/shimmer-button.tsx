"use client";

import type { ComponentPropsWithoutRef, CSSProperties } from "react";

import { cn } from "@/components/ui/cn";

interface ShimmerButtonProps extends ComponentPropsWithoutRef<"button"> {
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
}

/**
 * Conic-gradient "shimmer" CTA. The shimmer is a rotating conic gradient
 * masked to a thin ring; the inner background sits on top.
 *
 * Respects prefers-reduced-motion via the global media query in globals.css
 * (animation-duration → 0).
 */
export function ShimmerButton({
  shimmerColor = "#ffffff",
  shimmerSize = "0.08em",
  shimmerDuration = "3s",
  borderRadius = "9999px",
  background = "rgba(225, 6, 0, 0.95)",
  className,
  children,
  ...props
}: ShimmerButtonProps) {
  return (
    <button
      {...props}
      style={
        {
          "--spread": "90deg",
          "--shimmer-color": shimmerColor,
          "--radius": borderRadius,
          "--speed": shimmerDuration,
          "--cut": shimmerSize,
          "--bg": background,
        } as CSSProperties
      }
      className={cn(
        "group relative z-0 flex cursor-pointer items-center justify-center overflow-hidden whitespace-nowrap px-6 py-3 text-white",
        "[background:var(--bg)] [border-radius:var(--radius)]",
        "transition-transform duration-300 active:translate-y-px",
        "border border-white/10",
        "shadow-[0_0_0_1px_rgba(255,255,255,0.04)_inset,0_-8px_24px_rgba(255,255,255,0.06)_inset]",
        className,
      )}
    >
      {/* spark container */}
      <div
        className={cn(
          "absolute inset-0 overflow-visible [container-type:size]",
        )}
      >
        <div
          className={cn(
            "absolute inset-0 h-[100cqh] animate-shimmer-slide [aspect-ratio:1] [border-radius:0]",
            "[mask:none]",
          )}
        >
          <div
            className={cn(
              "animate-spin-around absolute -inset-full w-auto rotate-0",
              "[background:conic-gradient(from_calc(270deg-(var(--spread)*0.5)),transparent_0,var(--shimmer-color)_var(--spread),transparent_var(--spread))]",
              "[translate:0_0]",
            )}
          />
        </div>
      </div>

      {children}

      {/* Highlight on top */}
      <div
        className={cn(
          "insert-0 absolute size-full",
          "rounded-[inherit] px-4 py-1.5 text-sm font-medium shadow-[inset_0_-8px_10px_#ffffff12]",
          "transform-gpu transition-all duration-300 ease-in-out",
          "group-hover:shadow-[inset_0_-6px_10px_#ffffff20]",
          "group-active:shadow-[inset_0_-10px_10px_#ffffff20]",
        )}
      />

      {/* backdrop */}
      <div
        className={cn(
          "absolute -z-20 [background:var(--bg)] [border-radius:var(--radius)] [inset:var(--cut)]",
        )}
      />
    </button>
  );
}
