"use client";

import { useReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "./cn";

interface LoadingTireProps {
  size?: number;
  label?: string;
  className?: string;
}

/**
 * Cinematic loading indicator: animated F1-style tire silhouette.
 * Pure SVG + CSS — no Lottie payload — keeps it on the critical path
 * for first-paint loading states.
 */
export default function LoadingTire({ size = 56, label, className }: LoadingTireProps) {
  const reduced = useReducedMotion();
  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 56 56"
        role="img"
        aria-label={label ?? "Loading"}
        className={reduced ? "" : "animate-spin"}
        style={{ animationDuration: "1.4s" }}
      >
        <defs>
          <radialGradient id="tire-grad" cx="50%" cy="50%" r="50%">
            <stop offset="40%" stopColor="#1a1d22" />
            <stop offset="100%" stopColor="#0a0b0e" />
          </radialGradient>
        </defs>
        {/* Tire body */}
        <circle cx="28" cy="28" r="26" fill="url(#tire-grad)" stroke="#1f2127" strokeWidth="1" />
        {/* Inner hub */}
        <circle cx="28" cy="28" r="10" fill="#0c0d10" stroke="var(--accent-live)" strokeWidth="1.5" />
        {/* 5-spoke + 1 accent telemetry arc */}
        {[0, 72, 144, 216, 288].map((angle) => (
          <rect
            key={angle}
            x="27"
            y="6"
            width="2"
            height="14"
            rx="1"
            fill="var(--text-muted)"
            transform={`rotate(${angle} 28 28)`}
          />
        ))}
        <circle
          cx="28"
          cy="28"
          r="24"
          fill="none"
          stroke="var(--accent-live)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="38 200"
          opacity="0.85"
        />
      </svg>
      {label && (
        <p className="text-xs font-mono uppercase tracking-[0.18em] text-[color:var(--text-muted)]">
          {label}
        </p>
      )}
    </div>
  );
}
