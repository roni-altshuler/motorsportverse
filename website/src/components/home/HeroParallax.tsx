"use client";

import { BorderBeam } from "@/components/magicui/border-beam";
import { DotPattern } from "@/components/magicui/dot-pattern";

interface HeroParallaxProps {
  /**
   * Full-bleed hero photograph. When provided, renders the image at 0.55
   * opacity behind a top-to-bottom scrim. When omitted, the dot pattern is
   * exposed as the depth substrate.
   */
  trackImage?: string | null;
  /** Accepted for prop compatibility; no longer drives any gradient. */
  teamColor?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Hero band. Photographic backdrop (when trackImage present) on top of a
 * dot-pattern substrate, wrapped in a BorderBeam that traces the perimeter
 * with an F1-red → blue gradient.
 */
export default function HeroParallax({
  trackImage = null,
  children,
  className,
}: HeroParallaxProps) {
  return (
    <section className={`hero-photo-band relative ${className ?? ""}`}>
      {/* dot-pattern substrate — visible when no track image */}
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
      <BorderBeam
        size={1}
        duration={12}
        colorFrom="#E10600"
        colorTo="#3671C6"
        borderRadius={0}
      />
    </section>
  );
}
