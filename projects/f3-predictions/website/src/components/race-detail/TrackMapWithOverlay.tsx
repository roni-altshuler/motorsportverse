"use client";

import CircuitMap from "@/components/race-detail/CircuitMap";
import HUDPanel from "@/components/ui/HUDPanel";
import type { CircuitGeometry } from "@/types/circuit";

interface TrackMapWithOverlayProps {
  /** Vector geometry (F1 fastest-lap telemetry, shared circuits). */
  geometry?: CircuitGeometry | null;
  kicker?: string;
  title?: string;
  className?: string;
}

/**
 * Premium circuit panel. The F3 CLAUDE.md forbids a bare circuit image — the
 * clean monochrome `CircuitMap` SVG is always framed inside a `HUDPanel` so it
 * reads as a designed telemetry surface rather than a raw export. F3 ships only
 * vector geometry (no matplotlib PNG fallback), so when geometry is missing we
 * render a framed "layout unavailable" state instead of a naked image.
 */
export default function TrackMapWithOverlay({
  geometry,
  kicker = "Circuit",
  title = "Track Map",
  className = "mb-8",
}: TrackMapWithOverlayProps) {
  const hasGeometry = !!geometry && !!geometry.path;

  return (
    <HUDPanel
      kicker={kicker}
      title={title}
      rightSlot={
        <span className="eyebrow">{hasGeometry ? "Vector layout" : "Layout pending"}</span>
      }
      className={className}
      bodyClassName="p-0"
    >
      <div className="relative overflow-hidden bg-[color:var(--canvas)]">
        {/* Vignette + scanline overlay so the SVG reads as a framed HUD surface. */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 z-[1]"
          style={{
            background:
              "radial-gradient(120% 90% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
          }}
        />
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 z-[1] opacity-40"
          style={{ background: "var(--gradient-scanline)" }}
        />
        {hasGeometry ? (
          <div className="aspect-[16/9] w-full p-6">
            <CircuitMap
              geometry={geometry!}
              showCorners
              strokeWidth={2}
              accentColor="var(--accent)"
            />
          </div>
        ) : (
          <div className="flex aspect-[16/9] w-full items-center justify-center">
            <p className="eyebrow">Circuit layout unavailable</p>
          </div>
        )}
      </div>
    </HUDPanel>
  );
}
