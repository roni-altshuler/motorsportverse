"use client";

import { useEffect, useRef, useState, type ComponentPropsWithoutRef } from "react";
import { useInView, useMotionValue, useSpring } from "framer-motion";

import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/components/ui/cn";

interface NumberTickerProps extends ComponentPropsWithoutRef<"span"> {
  value: number;
  startValue?: number;
  direction?: "up" | "down";
  delay?: number;
  decimalPlaces?: number;
}

/**
 * Spring-driven number counter. Triggers when scrolled into view.
 * Falls back to the final value instantly under `prefers-reduced-motion`.
 */
export function NumberTicker({
  value,
  startValue = 0,
  direction = "up",
  delay = 0,
  className,
  decimalPlaces = 0,
  ...props
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const motionValue = useMotionValue(direction === "down" ? value : startValue);
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 100,
  });
  const isInView = useInView(ref, { once: true, margin: "0px" });
  const [display, setDisplay] = useState<string>(() =>
    Intl.NumberFormat("en-US", {
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
    }).format(direction === "down" ? value : startValue),
  );

  useEffect(() => {
    if (!isInView) return;
    if (reduced) {
      // Snap to the final value via the spring's source motion value rather
      // than setState — the spring listener below mirrors it to local state.
      motionValue.jump(value);
      return;
    }
    const timer = window.setTimeout(() => {
      motionValue.set(direction === "down" ? startValue : value);
    }, delay * 1000);
    return () => window.clearTimeout(timer);
  }, [motionValue, isInView, delay, value, direction, startValue, reduced]);

  useEffect(() => {
    const source = reduced ? motionValue : springValue;
    const unsubscribe = source.on("change", (latest) => {
      setDisplay(
        Intl.NumberFormat("en-US", {
          minimumFractionDigits: decimalPlaces,
          maximumFractionDigits: decimalPlaces,
        }).format(Number(latest.toFixed(decimalPlaces))),
      );
    });
    return () => unsubscribe();
  }, [springValue, motionValue, decimalPlaces, reduced]);

  return (
    <span
      ref={ref}
      className={cn("inline-block tabular-nums", className)}
      {...props}
    >
      {display}
    </span>
  );
}
