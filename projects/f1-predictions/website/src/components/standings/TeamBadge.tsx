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
   * falls back to the team's initials.
   */
  logoUrl?: string | null;
  /**
   * "badge" (default) — small circular avatar suitable for inline
   * table cells. "card" — larger rounded-square tile for prominent
   * constructor showcases and championship-forecast rows.
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

/**
 * Uniform light chip backdrop for every team. The logo assets are normalised
 * (see `lib/teamLogo.ts`) so all marks share one optical footprint; a light
 * field keeps every logo legible (several are dark / monochrome and vanish on
 * a dark tint), and the team colour comes through as the ring — consistent and
 * professional across the whole grid rather than per-logo guesswork.
 */
const CHIP_BG = "rgba(244,245,247,0.97)";

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
  const ring = teamColor || "var(--team-color, var(--hairline-strong))";

  // Inner padding scales with badge size so the normalised logo never kisses
  // the ring at any scale.
  const innerPad = Math.max(3, Math.round(size * 0.1));
  const innerSize = size - innerPad * 2;
  const isCard = variant === "card";

  return (
    <span
      data-team={team}
      aria-label={team}
      className={cn(
        "inline-flex items-center justify-center border shrink-0 overflow-hidden",
        isCard ? "rounded-[12px]" : "rounded-full",
        className,
      )}
      style={{
        width: size,
        height: size,
        padding: innerPad,
        background: CHIP_BG,
        borderColor: `color-mix(in srgb, ${ring} 70%, transparent)`,
        boxShadow: isCard
          ? `0 0 0 1px color-mix(in srgb, ${ring} 30%, transparent), 0 6px 18px color-mix(in srgb, ${ring} 14%, transparent)`
          : `inset 0 0 0 1px color-mix(in srgb, ${ring} 30%, transparent)`,
      }}
      title={team}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={team}
          width={innerSize}
          height={innerSize}
          style={{ width: innerSize, height: innerSize, objectFit: "contain" }}
          loading="lazy"
          decoding="async"
          onError={() => setSrc(null)}
        />
      ) : (
        <span
          className="font-display [font-weight:700] tracking-[0.04em]"
          style={{
            fontSize: Math.max(9, Math.round(size * (isCard ? 0.16 : 0.3))),
            color: "#111",
            lineHeight: 1.1,
            textAlign: "center",
          }}
        >
          {isCard ? team : teamInitials(team)}
        </span>
      )}
    </span>
  );
}
