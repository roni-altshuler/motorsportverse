"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { cn } from "@/components/ui/cn";

interface ChartContainerProps {
  /** Static PNG/WebP path to show as a crisp fallback before the React
   * chart hydrates.  Set to null to skip the fallback (e.g. when the
   * chart is the canonical render). */
  fallbackSrc?: string | null;
  fallbackAlt?: string;
  /** Fixed height in px to prevent layout shift while the React chart
   * hydrates. */
  height?: number;
  /** Defer chart hydration until the container scrolls into view. */
  lazy?: boolean;
  className?: string;
  children: React.ReactNode;
}

export default function ChartContainer({
  fallbackSrc,
  fallbackAlt = "",
  height = 360,
  lazy = true,
  className,
  children,
}: ChartContainerProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [hydrated, setHydrated] = useState(!lazy);
  const [showFallback, setShowFallback] = useState(true);

  useEffect(() => {
    if (!lazy) return;
    const el = ref.current;
    if (!el) return;
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

  useEffect(() => {
    if (!hydrated) return;
    // Allow the chart to paint, then fade out the fallback.
    const t = setTimeout(() => setShowFallback(false), 220);
    return () => clearTimeout(t);
  }, [hydrated]);

  return (
    <div
      ref={ref}
      className={cn("relative", className)}
      style={{ height }}
    >
      {fallbackSrc && showFallback && (
        <Image
          src={fallbackSrc}
          alt={fallbackAlt}
          fill
          unoptimized
          className={cn(
            "object-contain transition-opacity duration-300",
            hydrated ? "opacity-0" : "opacity-100",
          )}
        />
      )}
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
