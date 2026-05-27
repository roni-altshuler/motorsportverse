"use client";

import { useState } from "react";

import { cn } from "@/components/ui/cn";
import { teamLogoUrl } from "@/lib/teamLogo";

interface TeamBadgeProps {
  team: string;
  teamColor?: string;
  size?: number;
  className?: string;
  /**
   * Optional explicit logo URL. When omitted the component derives a
   * conventional path from the team name via `teamLogoUrl()`. A 404
   * falls back to the team's initials inside a coloured ring.
   */
  logoUrl?: string | null;
}

function teamInitials(team: string): string {
  const parts = team.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return parts
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

/**
 * Circular constructor badge with auto-resolved team logo.
 *
 * - Tries `logoUrl` first (if explicitly passed).
 * - Falls back to the conventional logo path derived from the team
 *   name (e.g. "Mercedes" → `/team-logos/mercedes.svg`).
 * - Falls back AGAIN to a tinted initials badge if the asset is
 *   missing — so we never show a broken-image icon.
 *
 * Drop a transparent SVG into `public/team-logos/<slug>.svg` and the
 * badge picks it up automatically.
 */
export default function TeamBadge({
  team,
  teamColor,
  size = 48,
  className,
  logoUrl,
}: TeamBadgeProps) {
  const initialSrc = logoUrl ?? teamLogoUrl(team);
  const [src, setSrc] = useState<string | null>(initialSrc);
  const bg = teamColor || "var(--team-color, var(--surface-elevated))";

  return (
    <span
      data-team={team}
      aria-label={team}
      className={cn(
        "inline-flex items-center justify-center rounded-full overflow-hidden border",
        className,
      )}
      style={{
        width: size,
        height: size,
        background: "rgba(0,0,0,0.4)",
        borderColor: bg,
        boxShadow: `inset 0 0 0 2px ${bg}`,
      }}
      title={team}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={team}
          width={size}
          height={size}
          style={{
            width: size * 0.7,
            height: size * 0.7,
            objectFit: "contain",
          }}
          loading="lazy"
          onError={() => setSrc(null)}
        />
      ) : (
        <span
          className="font-display [font-weight:700] tracking-[0.04em]"
          style={{
            fontSize: Math.max(10, Math.round(size * 0.28)),
            color: bg,
            lineHeight: 1,
          }}
        >
          {teamInitials(team)}
        </span>
      )}
    </span>
  );
}
