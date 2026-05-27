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
  /**
   * "badge" (default) — small circular avatar suitable for inline
   * table cells; renders the logo cropped inside a coloured ring.
   * "card" — larger rectangular tile suitable for prominent
   * constructor showcases and championship-forecast rows; renders
   * the full vertical logo (emblem + wordmark + small subtitle)
   * without a circular crop.
   */
  variant?: "badge" | "card";
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

export default function TeamBadge({
  team,
  teamColor,
  size = 48,
  className,
  logoUrl,
  variant = "badge",
}: TeamBadgeProps) {
  const initialSrc = logoUrl ?? teamLogoUrl(team);
  const [src, setSrc] = useState<string | null>(initialSrc);
  const bg = teamColor || "var(--team-color, var(--surface-elevated))";

  if (variant === "card") {
    return (
      <span
        data-team={team}
        aria-label={team}
        className={cn(
          "inline-flex items-center justify-center overflow-hidden rounded-[12px] border",
          className,
        )}
        style={{
          width: size,
          height: size,
          background: "rgba(0,0,0,0.4)",
          borderColor: `color-mix(in srgb, ${bg} 50%, transparent)`,
          boxShadow: `0 0 0 1px color-mix(in srgb, ${bg} 25%, transparent), 0 8px 24px color-mix(in srgb, ${bg} 18%, transparent)`,
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
              width: size * 0.86,
              height: size * 0.86,
              objectFit: "contain",
            }}
            loading="lazy"
            onError={() => setSrc(null)}
          />
        ) : (
          <span
            className="font-display [font-weight:900] tracking-[0.06em] uppercase"
            style={{
              fontSize: Math.max(12, Math.round(size * 0.16)),
              color: bg,
              lineHeight: 1.1,
              textAlign: "center",
            }}
          >
            {team}
          </span>
        )}
      </span>
    );
  }

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
