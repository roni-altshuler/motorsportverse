"use client";

import { Badge } from "@/components/ui/Badge";
import { computeRaceVolatility } from "@/lib/raceVolatility";
import type { ClassificationEntry } from "@/types/f3";

interface RaceVolatilityBadgeProps {
  classification: ClassificationEntry[] | null | undefined;
  /** Compact rendering — moves the description to the tooltip (for narrow rows). */
  compact?: boolean;
  className?: string;
}

/**
 * Small chip summarising how confident the per-race forecast is.
 *
 * Wording is intentionally model-agnostic: we say "High Confidence",
 * "Moderate Volatility", or "Chaotic Race" — never any internal
 * terminology. See {@link computeRaceVolatility} for the scoring logic
 * and bucket boundaries.
 */
export default function RaceVolatilityBadge({
  classification,
  compact = false,
  className,
}: RaceVolatilityBadgeProps) {
  const volatility = computeRaceVolatility(classification);
  if (!volatility) return null;

  // Map buckets onto the existing Badge variants. `positive` is the green
  // pill, `live` is the F3-blue pill; the moderate case re-uses the inline
  // style hook on Badge to recolour amber since the system has no amber variant.
  const variant =
    volatility.bucket === "high"
      ? "positive"
      : volatility.bucket === "chaotic"
        ? "live"
        : "default";

  const amberStyle =
    volatility.bucket === "moderate"
      ? {
          borderColor: "rgba(212, 160, 23, 0.45)",
          color: "var(--warning)",
        }
      : undefined;

  return (
    <Badge
      variant={variant}
      className={className}
      style={amberStyle}
      title={compact ? volatility.description : undefined}
      aria-label={`Race forecast: ${volatility.label}. ${volatility.description}`}
    >
      {volatility.label}
    </Badge>
  );
}
