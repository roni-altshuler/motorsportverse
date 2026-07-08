"use client";

import { Badge } from "@/components/ui/Badge";
import type { GridProvenance } from "@/types";

interface GridProvenanceBadgeProps {
  provenance: GridProvenance | null | undefined;
  className?: string;
}

/**
 * Small provenance chip for the starting grid behind a round's prediction.
 *
 *   "real-quali-verified" — the forecast was frozen after qualifying on the
 *                           round-verified official grid (green)
 *   "estimated"           — the grid was estimated, qualifying data wasn't in
 *                           (amber, reuses the RaceVolatilityBadge inline-amber
 *                           idiom since the design system has no amber variant)
 *   "stale"               — grid data present but not re-verified (muted)
 *
 * Renders nothing when provenance is absent (preview rounds, pre-overhaul
 * archived JSONs) — the page must not guess.
 */
export default function GridProvenanceBadge({ provenance, className }: GridProvenanceBadgeProps) {
  if (!provenance) return null;

  if (provenance === "real-quali-verified") {
    return (
      <Badge
        variant="positive"
        className={className}
        title="This prediction was frozen after qualifying, using the verified official starting grid."
        aria-label="Prediction frozen post-qualifying on the verified starting grid"
      >
        Frozen Post-Quali · Verified Grid
      </Badge>
    );
  }

  if (provenance === "estimated") {
    return (
      <Badge
        variant="default"
        className={className}
        style={{ borderColor: "rgba(212, 160, 23, 0.45)", color: "var(--warning)" }}
        title="Qualifying data was not available for this forecast — the starting grid is estimated."
        aria-label="Prediction built on an estimated starting grid"
      >
        Estimated Grid
      </Badge>
    );
  }

  if (provenance === "stale") {
    return (
      <Badge
        variant="muted"
        className={className}
        title="The starting grid behind this forecast could not be re-verified against the official source."
        aria-label="Starting grid data could not be re-verified"
      >
        Unverified Grid
      </Badge>
    );
  }

  // Unknown future provenance values: stay silent rather than mislabel.
  return null;
}
