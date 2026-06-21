"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";
import type { CircuitGeometry } from "@/types";

interface HeroParallaxProps {
  /**
   * Full-bleed hero photograph. When provided, renders the image at 0.55
   * opacity behind a top-to-bottom scrim. When omitted, the dot pattern is
   * exposed as the depth substrate.
   */
  trackImage?: string | null;
  /** Accepted for prop compatibility; no longer drives any gradient. */
  teamColor?: string;
  /**
   * SVG vector geometry for the featured race's circuit. When present, an
   * animated "comet" sweep traces the track behind the hero copy. The dash
   * trick keeps every closed-loop path in motion regardless of total length.
   */
  geometry?: CircuitGeometry | null;
  children: React.ReactNode;
  className?: string;
}

/**
 * Hero band. Dot-pattern substrate plus, when geometry is supplied, an
 * animated circuit-ribbon sweep that ties the hero visually to the upcoming
 * Grand Prix. All animation runs through a single CSS keyframe so the global
 * `prefers-reduced-motion` guard in `globals.css` neutralises it.
 */
export default function HeroParallax({
  trackImage = null,
  geometry = null,
  children,
  className,
}: HeroParallaxProps) {
  return (
    <section className={`hero-photo-band relative ${className ?? ""}`}>
      {!trackImage && (
        <DotPattern
          className="opacity-[0.06] [mask-image:radial-gradient(ellipse_at_center,white,transparent_75%)]"
          width={20}
          height={20}
          cr={1}
        />
      )}
      {trackImage && (
        <div
          aria-hidden
          className="hero-photo-band__image"
          style={{ backgroundImage: `url("${trackImage}")` }}
        />
      )}
      {geometry?.path && (
        <div aria-hidden className="hero-track-ribbon">
          <svg
            viewBox={geometry.viewBox}
            preserveAspectRatio="xMidYMid meet"
            role="presentation"
          >
            <defs>
              <linearGradient
                id="hero-track-gradient"
                x1="0%"
                y1="0%"
                x2="100%"
                y2="100%"
              >
                <stop offset="0%" stopColor="#E10600" />
                <stop offset="50%" stopColor="#FFFFFF" />
                <stop offset="100%" stopColor="#3671C6" />
              </linearGradient>
            </defs>
            <path className="ribbon-base" d={geometry.path} />
            <path className="ribbon-sweep-trail" d={geometry.path} />
            <path className="ribbon-sweep" d={geometry.path} />
          </svg>
        </div>
      )}
      <div aria-hidden className="hero-photo-band__scrim" />
      <div className="hero-photo-band__content">{children}</div>
    </section>
  );
}
