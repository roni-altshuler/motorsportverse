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

/**
 * Per-team optical-scale multiplier. Source logos vary wildly in
 * aspect ratio and content density: a circular Ferrari word-mark
 * reads small, while the Red Bull bull pre-fills the frame. To make
 * every logo carry the same perceived weight on the page we nudge
 * each one by an empirical multiplier within roughly [0.85, 1.15].
 *
 * Lower number == logo renders smaller (used for already-dense art
 * like Aston Martin's wings or the Red Bull bull).
 * Higher number == logo renders larger (used for text-heavy or
 * sparse art like Ferrari's word-mark or Williams' wordmark).
 *
 * Tweak free; keep within ±15% so the row never feels uneven.
 */
const OPTICAL_SCALE: Record<string, number> = {
  Ferrari: 1.12,        // tall slim word-mark inside a circle
  Williams: 1.10,       // thin text wordmark
  Mercedes: 0.92,       // three-pointed star fills aggressively
  "Red Bull Racing": 0.90, // bull motif already dense
  "Aston Martin": 0.90, // wings emblem fills the frame
  McLaren: 1.0,
  Alpine: 1.0,
  "Racing Bulls": 1.0,
  Haas: 1.05,           // slim "H" mark
  Audi: 1.05,           // four rings read narrow
  Cadillac: 0.98,
};

/**
 * Some logos are dark (graphite, navy, black) and would disappear on
 * a dark theme. We slap a subtle light backdrop just for those.
 * Everything else uses the team-colour tinted backdrop.
 */
const DARK_LOGO_TEAMS = new Set<string>([
  "Mercedes",      // wordmark is mid-grey text
  "Haas",          // outlined mark, no fill
  "Williams",      // dark navy wordmark
  "Aston Martin",  // dark green emblem on transparent
  "Cadillac",      // dark crest
  "Audi",          // dark rings
]);

function backdropFor(team: string, teamColor: string): string {
  if (DARK_LOGO_TEAMS.has(team)) {
    // Soft white wash so dark vector marks remain readable
    return "rgba(255,255,255,0.92)";
  }
  // Subtle tint of the team colour over a near-black base
  return `color-mix(in srgb, ${teamColor} 8%, rgba(15,17,22,0.85))`;
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
  const opticalScale = OPTICAL_SCALE[team] ?? 1.0;
  const backdrop = backdropFor(team, bg);

  // Inner padding scales with badge size — keeps logos from kissing
  // the container edge at any scale, but never balloons on big cards.
  const innerPad = Math.max(2, Math.round(size * 0.08));

  if (variant === "card") {
    // Larger square tile suitable for constructor showcase cards and
    // the WCC forecast rows. Internal logo footprint is normalised so
    // every team reads at the same visual weight.
    const innerSize = (size - innerPad * 2) * opticalScale;
    return (
      <span
        data-team={team}
        aria-label={team}
        className={cn(
          "inline-flex items-center justify-center rounded-[12px] border shrink-0",
          className,
        )}
        style={{
          width: size,
          height: size,
          padding: innerPad,
          background: backdrop,
          borderColor: `color-mix(in srgb, ${bg} 45%, transparent)`,
          boxShadow: `0 0 0 1px color-mix(in srgb, ${bg} 22%, transparent), 0 6px 18px color-mix(in srgb, ${bg} 14%, transparent)`,
        }}
        title={team}
      >
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={team}
            style={{
              width: innerSize,
              height: innerSize,
              maxWidth: "100%",
              maxHeight: "100%",
              objectFit: "contain",
              imageRendering: "auto",
            }}
            loading="lazy"
            decoding="async"
            onError={() => setSrc(null)}
          />
        ) : (
          <span
            className="font-display [font-weight:900] tracking-[0.06em] uppercase"
            style={{
              fontSize: Math.max(12, Math.round(size * 0.16)),
              color: DARK_LOGO_TEAMS.has(team) ? "#111" : bg,
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

  // Compact circular badge for inline rows / tables.
  const innerSize = (size - innerPad * 2) * opticalScale;
  return (
    <span
      data-team={team}
      aria-label={team}
      className={cn(
        "inline-flex items-center justify-center rounded-full border shrink-0",
        className,
      )}
      style={{
        width: size,
        height: size,
        padding: innerPad,
        background: backdrop,
        borderColor: `color-mix(in srgb, ${bg} 75%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${bg} 35%, transparent)`,
      }}
      title={team}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={team}
          style={{
            width: innerSize,
            height: innerSize,
            maxWidth: "100%",
            maxHeight: "100%",
            objectFit: "contain",
            imageRendering: "auto",
          }}
          loading="lazy"
          decoding="async"
          onError={() => setSrc(null)}
        />
      ) : (
        <span
          className="font-display [font-weight:700] tracking-[0.04em]"
          style={{
            fontSize: Math.max(9, Math.round(size * 0.30)),
            color: DARK_LOGO_TEAMS.has(team) ? "#111" : bg,
            lineHeight: 1,
          }}
        >
          {teamInitials(team)}
        </span>
      )}
    </span>
  );
}
