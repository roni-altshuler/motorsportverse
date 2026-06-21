"use client";

import Image from "next/image";
import HUDPanel from "@/components/ui/HUDPanel";
import CircuitMap from "@/components/race-detail/CircuitMap";
import type { CircuitGeometry } from "@/types";

interface TrackMapWithOverlayProps {
  /** Vector geometry from `generate_circuit_svg.py`. Preferred when present. */
  geometry?: CircuitGeometry | null;
  /** Cold-start fallback: matplotlib PNG path. Used when geometry is null. */
  src: string;
  alt: string;
  onLightbox?: () => void;
  onError?: () => void;
  kicker?: string;
  title?: string;
}

/**
 * Premium circuit panel. When `geometry` is present (FastF1-derived SVG),
 * renders the clean monochrome `CircuitMap`; otherwise falls back to the
 * matplotlib PNG so cold-start rounds still surface something.
 */
export default function TrackMapWithOverlay({
  geometry,
  src,
  alt,
  onLightbox,
  onError,
  kicker = "Circuit",
  title = "Track Map",
}: TrackMapWithOverlayProps) {
  const hasGeometry = !!geometry && !!geometry.path;
  return (
    <HUDPanel
      kicker={kicker}
      title={title}
      rightSlot={
        <span className="eyebrow">
          {hasGeometry ? "Vector layout" : "Corners labelled"}
        </span>
      }
      className="mb-8"
    >
      <div className="relative overflow-hidden bg-[color:var(--canvas)]">
        {hasGeometry ? (
          <button
            type="button"
            className="block w-full text-left"
            onClick={onLightbox}
            aria-label="Open circuit map in lightbox"
          >
            <div className="aspect-[16/9] w-full cursor-zoom-in p-6">
              <CircuitMap
                geometry={geometry!}
                showCorners
                showDrsZones
                strokeWidth={2}
              />
            </div>
          </button>
        ) : (
          <button
            type="button"
            className="block w-full text-left"
            onClick={onLightbox}
            aria-label="Open track map in lightbox"
          >
            <Image
              src={src}
              alt={alt}
              width={1600}
              height={900}
              className="w-full h-auto cursor-zoom-in"
              style={{ width: "100%", height: "auto" }}
              onError={() => onError?.()}
              unoptimized
            />
          </button>
        )}
      </div>
    </HUDPanel>
  );
}
