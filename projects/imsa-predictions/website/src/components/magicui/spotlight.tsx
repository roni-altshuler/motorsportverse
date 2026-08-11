"use client";

import { useCallback, useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/components/ui/cn";

interface SpotlightProps {
  children?: ReactNode;
  className?: string;
  /** Diameter of the spotlight in px. */
  size?: number;
  /** Spotlight color. */
  color?: string;
}

/**
 * Cursor-following radial gradient spotlight. Wraps content and reveals a
 * soft circular highlight where the cursor sits.
 */
export function Spotlight({
  children,
  className,
  size = 280,
  color = "rgba(255, 255, 255, 0.06)",
}: SpotlightProps) {
  const ref = useRef<HTMLDivElement>(null);

  const handleMove = useCallback((e: MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
    el.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.addEventListener("mousemove", handleMove);
    return () => el.removeEventListener("mousemove", handleMove);
  }, [handleMove]);

  return (
    <div
      ref={ref}
      className={cn("relative overflow-hidden", className)}
      style={
        {
          "--spot-color": color,
          "--spot-size": `${size}px`,
        } as React.CSSProperties
      }
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background:
            "radial-gradient(var(--spot-size) circle at var(--mouse-x) var(--mouse-y), var(--spot-color), transparent 70%)",
        }}
        aria-hidden
      />
      {children}
    </div>
  );
}
