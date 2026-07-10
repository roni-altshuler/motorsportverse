"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/components/ui/cn";

/**
 * Lazy hydration boundary for chart-library-heavy client charts — the FE
 * adaptation of the F1 flagship's ChartContainer. FE's charts ship no PNG
 * fallbacks (they are the canonical render), so this is a fixed-height,
 * IntersectionObserver-gated mount: the recharts tree only hydrates once the
 * container scrolls near the viewport, and the reserved height prevents CLS.
 */
interface ChartContainerProps {
  /** Fixed height in px to prevent layout shift while the chart hydrates. */
  height?: number;
  /** Defer chart hydration until the container scrolls into view. */
  lazy?: boolean;
  className?: string;
  children: React.ReactNode;
}

export default function ChartContainer({
  height = 320,
  lazy = true,
  className,
  children,
}: ChartContainerProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [hydrated, setHydrated] = useState(!lazy);

  useEffect(() => {
    if (!lazy) return;
    const el = ref.current;
    if (!el) return;
    // Headless/SSR/no-IO environments must never leave the chart unmounted.
    if (typeof IntersectionObserver === "undefined") {
      const id = window.requestAnimationFrame(() => setHydrated(true));
      return () => window.cancelAnimationFrame(id);
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setHydrated(true);
            io.disconnect();
            break;
          }
        }
      },
      { rootMargin: "150px 0px 150px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [lazy]);

  return (
    <div ref={ref} className={cn("relative", className)} style={{ height }}>
      <div
        className={cn(
          "absolute inset-0 transition-opacity duration-300",
          hydrated ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
      >
        {hydrated && children}
      </div>
    </div>
  );
}
