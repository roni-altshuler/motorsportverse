"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

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
 * Falls back to a static card under reduced motion (no JS animation loop,
 * the radial gradient simply doesn't update).
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
  const [pos, setPos] = useState({ x: -gradientSize, y: -gradientSize });

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    setPos({ x: -gradientSize, y: -gradientSize });
  }, [gradientSize]);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    el.addEventListener("mousemove", handleMouseMove);
    el.addEventListener("mouseleave", handleMouseLeave);
    return () => {
      el.removeEventListener("mousemove", handleMouseMove);
      el.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [handleMouseMove, handleMouseLeave]);

  const borderStyle: CSSProperties = {
    background: `radial-gradient(${gradientSize}px circle at ${pos.x}px ${pos.y}px, ${gradientFrom}, ${gradientTo}, transparent 60%)`,
    padding: "1px",
    WebkitMask: "linear-gradient(#000,#000) content-box, linear-gradient(#000,#000)",
    WebkitMaskComposite: "xor",
    maskComposite: "exclude",
  };

  const glowStyle: CSSProperties = {
    background: `radial-gradient(${gradientSize}px circle at ${pos.x}px ${pos.y}px, ${gradientColor}, transparent 100%)`,
    opacity: gradientOpacity,
  };

  return (
    <div
      ref={cardRef}
      className={cn(
        "group relative overflow-hidden rounded-[var(--radius-card,4px)] bg-[var(--surface-card)]",
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={borderStyle}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        style={glowStyle}
        aria-hidden
      />
      <div className="relative z-10 h-full w-full">{children}</div>
    </div>
  );
}
