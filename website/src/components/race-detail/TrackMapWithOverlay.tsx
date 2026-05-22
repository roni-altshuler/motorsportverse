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
  kicker?: string;
  title?: string;
}

/**
 * Track-map figure wrapped in a HUD frame.  The PNG is the geometric
 * source of truth; we lay an SVG sweep + vignette + scanline on top
 * so the figure reads as part of the broadcast-HUD vocabulary rather
 * than a raw matplotlib export.
 */
export default function TrackMapWithOverlay({
  src,
  alt,
  onLightbox,
  onError,
  kicker = "Circuit",
  title = "Track Map",
}: TrackMapWithOverlayProps) {
  const wrap = useRef<HTMLDivElement | null>(null);
  const sweep = useRef<SVGRectElement | null>(null);

  useGSAPScrollTrigger(
    wrap,
    (gsap, ScrollTrigger, el) => {
      if (!sweep.current) return;
      const tl = gsap.to(sweep.current, {
        attr: { x: "110%" },
        ease: "none",
        scrollTrigger: {
          trigger: el,
          start: "top 85%",
          end: "bottom 25%",
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
      kicker={kicker}
      title={title}
      cornerNotch
      rightSlot={
        <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-[color:var(--text-muted)]">
          Corners labelled
        </span>
      }
      className="mb-8"
    >
      <div
        ref={wrap}
        className="relative rounded-lg overflow-hidden group"
        style={{
          background:
            "radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--accent-live) 8%, transparent) 0%, transparent 60%), var(--surface-elevated)",
          border: "1px solid var(--border-strong)",
        }}
      >
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
            className="w-full h-auto cursor-zoom-in transition-transform duration-500 group-hover:scale-[1.01]"
            style={{
              width: "100%",
              height: "auto",
              filter: "contrast(1.08) brightness(1.04) saturate(0.85)",
              mixBlendMode: "screen",
            }}
            onError={() => onError?.()}
            unoptimized
          />
        </button>

        {/* Vignette + scanlines + edge sweep — all CSS/SVG, gives the
            figure a broadcast-HUD feel rather than a raw matplotlib look. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at center, transparent 55%, color-mix(in srgb, var(--bg) 60%, transparent) 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-25"
          style={{
            background: "var(--gradient-scanline)",
            mixBlendMode: "overlay",
          }}
        />
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="track-sweep" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="rgba(247, 107, 21, 0)" />
              <stop offset="50%" stopColor="rgba(247, 107, 21, 0.35)" />
              <stop offset="100%" stopColor="rgba(247, 107, 21, 0)" />
            </linearGradient>
          </defs>
          <rect
            ref={sweep}
            x="-25%"
            y="0"
            width="25%"
            height="100%"
            fill="url(#track-sweep)"
          />
        </svg>
      </div>
    </HUDPanel>
  );
}
