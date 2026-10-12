"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";
import type { CircuitGeometry } from "@/types";

interface HeroParallaxProps {
  /**
   * Full-bleed hero photograph. When provided, renders the image at 0.45
   * opacity behind a top-to-bottom scrim. When omitted, the dot pattern is
   * exposed as the depth substrate.
   */
  trackImage?: string | null;
  /** Accepted for prop compatibility; no longer drives any gradient. */
  teamColor?: string;
  /** Static hero surface; legacy geometry props never render a backdrop. */
  geometry?: CircuitGeometry | null;
  children: React.ReactNode;
  className?: string;
}

/** Static hero surface; legacy geometry props never render a backdrop. */
export default function HeroParallax({
  trackImage = null,
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
      <div aria-hidden className="hero-photo-band__scrim" />
      <div className="hero-photo-band__content">{children}</div>
    </section>
  );
}
