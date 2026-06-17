"use client";

import { cn } from "@/components/ui/cn";

interface TeamBadgeProps {
  team: string;
  teamColor?: string;
  size?: number;
  className?: string;
  /**
   * "badge" (default) — small circular initials chip for inline table cells.
   * "card" — larger rounded-square tile for prominent team showcases and the
   * championship-forecast rows.
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
 * F2 team mark. No team-logo assets ship for F2 yet, so this renders a polished
 * team-coloured initials chip (port of the RaceIQ F1 TeamBadge, minus the logo
 * image path — per the "don't add new image URLs" rule). The team colour comes
 * through as the ring; a uniform light field keeps the initials legible.
 */
const CHIP_BG = "rgba(244,245,247,0.97)";

export default function TeamBadge({
  team,
  teamColor,
  size = 48,
  className,
  variant = "badge",
}: TeamBadgeProps) {
  const ring = teamColor || "var(--team-color, var(--hairline-strong))";
  const innerPad = Math.max(3, Math.round(size * 0.1));
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
    </span>
  );
}
