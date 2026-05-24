"use client";

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
 * F1.com-style 64px circular driver portrait. Team color background, white
 * letters fallback when no headshot is available.
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
  const bg = teamColor || "var(--team-color, var(--surface-elevated))";
  const resolvedSrc = resolveHeadshotSrc(headshotUrl);
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
      {resolvedSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={resolvedSrc}
          alt={driverFullName ?? driver}
          width={size}
          height={size}
          style={{ objectFit: "cover", width: size, height: size }}
          loading="lazy"
        />
      ) : (
        <span
          className="font-display [font-weight:700] text-white tracking-[0.04em]"
          style={{
            fontSize: Math.max(12, Math.round(size * 0.34)),
            lineHeight: 1,
            textShadow: "0 1px 2px rgba(0,0,0,0.6)",
          }}
        >
          {driver}
        </span>
      )}
    </span>
  );
}
