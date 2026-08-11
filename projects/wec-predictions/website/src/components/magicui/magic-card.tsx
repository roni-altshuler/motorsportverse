"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/components/ui/cn";

interface MagicCardProps {
  children?: ReactNode;
  className?: string;
  /** Diameter of the cursor-following gradient in px. */
  gradientSize?: number;
  gradientColor?: string;
  gradientOpacity?: number;
  /** Color of the 1px border highlight that traces the cursor. */
  gradientFrom?: string;
  gradientTo?: string;
}

/**
 * Cursor-tracking gradient card. The inner gradient follows the mouse;
 * a thinner border-gradient traces the cursor on top.
 *
 * Gradient updates are batched into a single requestAnimationFrame per
 * frame and written straight to the DOM via refs — React never re-renders
 * during mousemove. Reduced-motion users skip the JS loop entirely; the
 * card stays static and the hover-fade still works via CSS opacity.
 */
export function MagicCard({
  children,
  className,
  gradientSize = 220,
  gradientColor = "#262626",
  gradientOpacity = 0.6,
  gradientFrom = "#E10600",
  gradientTo = "#3671C6",
}: MagicCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const borderRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = cardRef.current;
    const borderEl = borderRef.current;
    const glowEl = glowRef.current;
    if (!el || !borderEl || !glowEl) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Initial off-screen position so the gradient is hidden before first hover.
    const writePosition = (x: number, y: number) => {
      borderEl.style.background = `radial-gradient(${gradientSize}px circle at ${x}px ${y}px, ${gradientFrom}, ${gradientTo}, transparent 60%)`;
      glowEl.style.background = `radial-gradient(${gradientSize}px circle at ${x}px ${y}px, ${gradientColor}, transparent 100%)`;
    };
    writePosition(-gradientSize, -gradientSize);

    if (reduced) {
      // Reduced motion: skip the listener entirely; CSS opacity transition still
      // fades the static gradients in/out on hover.
      return;
    }

    let pendingFrame: number | null = null;
    let nextX = -gradientSize;
    let nextY = -gradientSize;

    const flush = () => {
      pendingFrame = null;
      writePosition(nextX, nextY);
    };

    const handleMouseMove = (event: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      nextX = event.clientX - rect.left;
      nextY = event.clientY - rect.top;
      if (pendingFrame !== null) return;
      pendingFrame = requestAnimationFrame(flush);
    };

    const handleMouseLeave = () => {
      nextX = -gradientSize;
      nextY = -gradientSize;
      if (pendingFrame !== null) return;
      pendingFrame = requestAnimationFrame(flush);
    };

    el.addEventListener("mousemove", handleMouseMove, { passive: true });
    el.addEventListener("mouseleave", handleMouseLeave, { passive: true });

    return () => {
      el.removeEventListener("mousemove", handleMouseMove);
      el.removeEventListener("mouseleave", handleMouseLeave);
      if (pendingFrame !== null) cancelAnimationFrame(pendingFrame);
    };
  }, [gradientSize, gradientColor, gradientFrom, gradientTo]);

  return (
    <div
      ref={cardRef}
      className={cn(
        "group relative overflow-hidden rounded-[var(--radius-card,4px)] bg-[var(--surface-card)]",
        className,
      )}
    >
      <div
        ref={borderRef}
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{
          padding: "1px",
          WebkitMask:
            "linear-gradient(#000,#000) content-box, linear-gradient(#000,#000)",
          WebkitMaskComposite: "xor",
          maskComposite: "exclude",
        }}
        aria-hidden
      />
      <div
        ref={glowRef}
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={{ opacity: gradientOpacity }}
        aria-hidden
      />
      <div className="relative z-10 h-full w-full">{children}</div>
    </div>
  );
}
