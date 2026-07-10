"use client";

import { useEffect, useRef } from "react";
import { animate, useInView, useMotionValue, useTransform } from "framer-motion";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { DURATIONS, EASE } from "@/lib/motion";
import { cn } from "./cn";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  format?: (n: number) => string;
  className?: string;
  variant?: "default" | "huge" | "compact";
  /** Wait until in view before counting. Defaults to true. */
  whenInView?: boolean;
}

const VARIANT_CLASS: Record<NonNullable<AnimatedNumberProps["variant"]>, string> = {
  default: "title-md",
  huge: "display-lg",
  compact: "body-sm font-mono",
};

export function AnimatedNumber({
  value,
  duration = DURATIONS.glide,
  decimals,
  prefix,
  suffix,
  format,
  className,
  variant = "default",
  whenInView = true,
}: AnimatedNumberProps) {
  const reduced = useReducedMotion();
  const motionValue = useMotionValue(0);
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true, margin: "0px 0px -10% 0px" });
  const resolvedDecimals =
    decimals ?? (Number.isInteger(value) ? 0 : Math.min(3, (`${value}`.split(".")[1] || "").length));
  const display = useTransform(motionValue, (latest) => {
    const n = Number.isFinite(latest) ? latest : 0;
    if (format) return format(n);
    return n.toFixed(resolvedDecimals);
  });

  useEffect(() => {
    if (reduced) {
      motionValue.set(value);
      return;
    }
    if (whenInView && !inView) return;
    const controls = animate(motionValue, value, {
      duration,
      ease: EASE.pit,
    });
    return () => controls.stop();
  }, [value, duration, reduced, inView, whenInView, motionValue]);

  useEffect(() => {
    return display.on("change", (latest) => {
      if (ref.current) {
        ref.current.textContent = `${prefix ?? ""}${latest}${suffix ?? ""}`;
      }
    });
  }, [display, prefix, suffix]);

  return (
    <span
      ref={ref}
      className={cn("font-tabular tabular-nums", VARIANT_CLASS[variant], className)}
    >
      {`${prefix ?? ""}${format ? format(reduced ? value : 0) : (reduced ? value : 0).toFixed(resolvedDecimals)}${suffix ?? ""}`}
    </span>
  );
}

export default AnimatedNumber;
