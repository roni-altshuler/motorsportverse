"use client";

import { useState } from "react";

import { cn } from "@/components/ui/cn";

/**
 * F1.com-style circular driver portrait — ported verbatim from RaceIQ F1.
 * Shows /headshots/<CODE>.webp when available; otherwise renders a team-tinted
 * conic backdrop with a diagonal stripe + the 3-letter code. Same outer
 * dimensions in both states (no CLS). No real headshots ship for the paddock yet, so
 * the polished fallback IS the headshot; drop-in .webp's appear automatically.
 */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function resolveHeadshotSrc(headshotUrl?: string | null): string | null {
  if (!headshotUrl) return null;
  if (/^(https?:)?\/\//i.test(headshotUrl) || headshotUrl.startsWith("data:")) {
    return headshotUrl;
  }
  const normalized = headshotUrl.startsWith("/") ? headshotUrl : `/${headshotUrl}`;
  return `${BASE_PATH}${normalized}`;
}

interface DriverPortraitProps {
  /** 3-letter driver code (e.g. "MAR", "HAD"). Used as fallback inside the circle. */
  driver: string;
  /** Optional full name — used for the alt text. */
  driverFullName?: string;
  /** Team name (resolves --team-color via the [data-team] attribute). */
  team: string;
  /** Team color hex (overrides the resolved CSS var if provided). */
  teamColor?: string;
  /** Optional headshot URL — when present, displayed inside the circle. */
  headshotUrl?: string | null;
  /** Diameter in px. Default 64. */
  size?: number;
  /** Optional class on the outer wrapper. */
  className?: string;
}

export default function DriverPortrait({
  driver,
  driverFullName,
  team,
  teamColor,
  headshotUrl,
  size = 64,
  className,
}: DriverPortraitProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const bg = teamColor || "var(--team-color, var(--surface-elevated))";
  const candidate = headshotUrl || (driver ? `/headshots/${driver}.webp` : null);
  const resolvedSrc = resolveHeadshotSrc(candidate);
  const showFallback = !resolvedSrc || imageFailed;

  return (
    <span
      data-team={team}
      aria-label={driverFullName ?? driver}
      className={cn(
        "relative inline-flex items-center justify-center rounded-full overflow-hidden",
        className,
      )}
      style={{
        width: size,
        height: size,
        background: bg,
        boxShadow: `0 0 0 2px ${bg}, 0 1px 2px rgba(0,0,0,0.4)`,
      }}
    >
      {showFallback ? (
        <>
          <span
            aria-hidden
            className="absolute inset-0"
            style={{
              background: `conic-gradient(from 220deg, ${
                teamColor || "var(--team-color, var(--surface-elevated))"
              }, color-mix(in oklab, ${
                teamColor || "var(--team-color, #2a2a2a)"
              } 30%, #000) 60%, ${teamColor || "var(--team-color, var(--surface-elevated))"})`,
            }}
          />
          <span
            aria-hidden
            className="absolute inset-0"
            style={{
              background:
                "repeating-linear-gradient(45deg, rgba(255,255,255,0.06) 0 1px, transparent 1px 8px)",
            }}
          />
          <span
            className="relative font-mono text-white"
            style={{
              fontSize: Math.max(11, Math.round(size * 0.22)),
              lineHeight: 1,
              letterSpacing: "0.08em",
              textShadow: "0 1px 2px rgba(0,0,0,0.6)",
            }}
          >
            {driver}
          </span>
        </>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={resolvedSrc!}
          alt={driverFullName ?? driver}
          width={size}
          height={size}
          style={{ objectFit: "cover", width: size, height: size }}
          loading="lazy"
          onError={() => setImageFailed(true)}
        />
      )}
    </span>
  );
}
