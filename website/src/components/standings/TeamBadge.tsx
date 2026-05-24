"use client";

import { cn } from "@/components/ui/cn";

interface TeamBadgeProps {
  team: string;
  teamColor?: string;
  size?: number;
  className?: string;
  /** Optional logo URL. Initials fallback when omitted. */
  logoUrl?: string | null;
}

function teamInitials(team: string): string {
  const parts = team.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

/**
 * F1.com-style 48px circular constructor badge.
 */
export default function TeamBadge({
  team,
  teamColor,
  size = 48,
  className,
  logoUrl,
}: TeamBadgeProps) {
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
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt={team}
          width={size}
          height={size}
          style={{ width: size * 0.7, height: size * 0.7, objectFit: "contain" }}
          loading="lazy"
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
