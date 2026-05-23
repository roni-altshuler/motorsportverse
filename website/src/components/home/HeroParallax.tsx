"use client";

interface HeroParallaxProps {
  /**
   * Bugatti-style full-bleed hero photograph (per-round track_map.webp).
   * When provided, renders the image at 0.55 opacity behind a top-to-bottom
   * scrim. When omitted, the hero is pure black canvas.
   */
  trackImage?: string | null;
  /** Accepted for prop compatibility; no longer drives any gradient. */
  teamColor?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Bugatti redesign: gutted hero wrapper. The three-layer parallax + GSAP
 * scroll triggers + scanline overlay + telemetry-strip are removed. The
 * trackImage prop is now the primary depth element — full-bleed photograph
 * with scrim, matching DESIGN.md `hero-photo-band`.
 */
export default function HeroParallax({
  trackImage = null,
  children,
  className,
}: HeroParallaxProps) {
  return (
    <section
      className={`hero-photo-band ${className ?? ""}`}
    >
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
