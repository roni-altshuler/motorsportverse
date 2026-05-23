"use client";

import Image from "next/image";
import HUDPanel from "@/components/ui/HUDPanel";

interface TrackMapWithOverlayProps {
  src: string;
  alt: string;
  onLightbox?: () => void;
  onError?: () => void;
  kicker?: string;
  title?: string;
}

/**
 * Bugatti redesign: the orange sweep / vignette / scanline / mix-blend
 * filter / radial-gradient backdrop are all gone. The track map is now a
 * full-bleed photograph inside a flat hairline-bordered panel — Bugatti's
 * "photography as voltage" rule applied to the schematic circuit map.
 */
export default function TrackMapWithOverlay({
  src,
  alt,
  onLightbox,
  onError,
  kicker = "Circuit",
  title = "Track Map",
}: TrackMapWithOverlayProps) {
  return (
    <HUDPanel
      kicker={kicker}
      title={title}
      rightSlot={
        <span className="eyebrow">Corners labelled</span>
      }
      className="mb-8"
    >
      <div className="relative overflow-hidden bg-[color:var(--canvas)]">
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
      </div>
    </HUDPanel>
  );
}
