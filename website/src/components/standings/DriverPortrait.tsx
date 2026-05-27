"use client";

import { useState } from "react";

import { cn } from "@/components/ui/cn";

/**
 * Next.js basePath prefix.  The data layer (`export_website_data.py`) stores
 * headshot paths as `/headshots/<CODE>.webp` because the basePath is unknown
 * at Python build time — it's resolved here, on the React side, so the same
 * JSON works under both the GitHub Pages prefix and local `npm run dev`.
 */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function resolveHeadshotSrc(headshotUrl?: string | null): string | null {
  if (!headshotUrl) return null;
  // Absolute URLs (http(s) or data:) bypass the basePath prefix.
  if (/^(https?:)?\/\//i.test(headshotUrl) || headshotUrl.startsWith("data:")) {
    return headshotUrl;
  }
  // Treat anything else as a public-rooted path; ensure a single leading slash.
  const normalized = headshotUrl.startsWith("/") ? headshotUrl : `/${headshotUrl}`;
  return `${BASE_PATH}${normalized}`;
}

interface DriverPortraitProps {
  /** 3-letter driver code (e.g. "VER", "NOR"). Used as fallback inside the circle. */
  driver: string;
  /** Optional full name — used for the alt text. */
  driverFullName?: string;
  /** Team name (resolves --team-color via the [data-team] attribute). */
  team: string;
  /** Team color hex (overrides the resolved CSS var if provided). */
  teamColor?: string;
  /** Optional headshot URL — when present, displayed inside the circle. */
  headshotUrl?: string | null;
  /** Diameter in px. Default 64 (F1.com sizing). */
  size?: number;
  /** Optional class on the outer wrapper. */
  className?: string;
}

/**
 * F1.com-style circular driver portrait. Shows the headshot when available;
 * falls back to a team-tinted conic backdrop with a fine diagonal stripe and
 * the driver's 3-letter code. Same outer dimensions in both states — no CLS.
 */
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
  // When the data layer omits headshotUrl, synthesize the conventional asset
  // path `/headshots/<CODE>.webp`. onError below still falls back to the
  // conic-gradient avatar for reserves and mid-season debuts.
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
          {/* Conic backdrop — team color rotated through a darker variant for depth. */}
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
          {/* Subtle diagonal stripe overlay. */}
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
