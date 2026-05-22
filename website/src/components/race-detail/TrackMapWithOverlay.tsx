"use client";

import Image from "next/image";
import { useRef } from "react";
import HUDPanel from "@/components/ui/HUDPanel";
import { useGSAPScrollTrigger } from "@/lib/useGSAPScrollTrigger";

interface TrackMapWithOverlayProps {
  src: string;
  alt: string;
  onLightbox?: () => void;
  onError?: () => void;
}

/**
 * Track map wrapped in a HUDPanel.  The PNG remains the source of
 * truth (correct geometry from FastF1); SVG overlay sits on top to
 * draw a sweeping racing-line on scroll for cinematic effect.
 */
export default function TrackMapWithOverlay({ src, alt, onLightbox, onError }: TrackMapWithOverlayProps) {
  const wrap = useRef<HTMLDivElement | null>(null);
  const sweep = useRef<SVGRectElement | null>(null);

  useGSAPScrollTrigger(
    wrap,
    (gsap, ScrollTrigger, el) => {
      if (!sweep.current) return;
      const tl = gsap.to(sweep.current, {
        attr: { x: "100%" },
        ease: "none",
        scrollTrigger: {
          trigger: el,
          start: "top 80%",
          end: "bottom 30%",
          scrub: 0.7,
        },
      });
      return () => {
        tl.kill();
      };
    },
    [src],
  );

  return (
    <HUDPanel
      kicker="Circuit"
      title="Track Map"
      rightSlot={
        <span className="text-xs font-mono text-[color:var(--text-muted)]">Corners labelled</span>
      }
      className="mb-8"
    >
      <div ref={wrap} className="relative rounded-lg overflow-hidden" style={{ background: "var(--bg-surface)" }}>
        <button
          type="button"
          className="block w-full"
          onClick={onLightbox}
          aria-label="Open track map in lightbox"
        >
          <Image
            src={src}
            alt={alt}
            width={1600}
            height={900}
            className="viz-image w-full h-auto cursor-zoom-in"
            style={{ width: "100%", height: "auto" }}
            onError={() => onError?.()}
            unoptimized
          />
        </button>
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="track-sweep" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgba(247, 107, 21, 0)" />
              <stop offset="50%" stopColor="rgba(247, 107, 21, 0.25)" />
              <stop offset="100%" stopColor="rgba(247, 107, 21, 0)" />
            </linearGradient>
          </defs>
          <rect
            ref={sweep}
            x="-20%"
            y="0"
            width="20%"
            height="100%"
            fill="url(#track-sweep)"
          />
        </svg>
      </div>
    </HUDPanel>
  );
}
