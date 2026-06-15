"use client";

import { cn } from "./cn";

interface LoadingTireProps {
  /** Kept for prop compatibility; no longer used in the text-only spinner. */
  size?: number;
  label?: string;
  className?: string;
}

/**
 * Bugatti redesign: text-only loading indicator. The decorative tire SVG was
 * replaced with a quiet pulsing "LOADING" eyebrow per Bugatti restraint.
 */
export default function LoadingTire({ label, className }: LoadingTireProps) {
  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <p className="eyebrow loading-pulse">{label ?? "Loading"}</p>
    </div>
  );
}
