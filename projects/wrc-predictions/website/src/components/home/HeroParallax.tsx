"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";
import { surfaceColor as resolveSurfaceColor, surfaceLabel } from "@/lib/surface";

interface HeroParallaxProps {
  /**
   * Surface of the featured (next) rally — gravel / tarmac / snow. When present,
   * a prominent colour-coded surface chip is pinned in the hero. WRC has no fixed
   * course geometry, so surface (the single biggest driver of pace) takes the
   * place the F1 flagship gave to the animated track outline.
   */
  surface?: string | null;
  /** Explicit surface colour from the data (preferred over the fallback map). */
  surfaceColor?: string | null;
  children: React.ReactNode;
  className?: string;
}

/**
 * Hero band for RaceIQ WRC. Ported from the F1 HeroParallax, but WRC rounds are
 * run over public special stages rather than a fixed course, so there is no
 * track outline to trace. The radial-gradient backdrop and dot-pattern substrate
 * remain, and the featured rally's surface is surfaced as a prominent chip. The
 * global `prefers-reduced-motion` guard in globals.css still neutralises motion.
 */
export default function HeroParallax({
  children,
  className,
  surface = null,
  surfaceColor = null,
}: HeroParallaxProps) {
  const chipColor = resolveSurfaceColor(surface, surfaceColor);
  return (
    <section className={`hero-photo-band relative ${className ?? ""}`}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(80% 120% at 75% -10%, color-mix(in srgb, var(--accent) 16%, transparent), transparent 55%)",
        }}
      />
      <DotPattern
        className="opacity-[0.06] [mask-image:radial-gradient(ellipse_at_center,white,transparent_75%)]"
        width={20}
        height={20}
        cr={1}
      />
      {surface && (
        <div className="pointer-events-none absolute right-5 top-5 z-[3] sm:right-8 sm:top-8">
          <span
            className="surface-chip"
            data-surface={surface}
            style={{ "--surface-color": chipColor } as React.CSSProperties}
          >
            {surfaceLabel(surface)}
          </span>
        </div>
      )}
      <div aria-hidden className="hero-photo-band__scrim" />
      <div className="hero-photo-band__content">{children}</div>
    </section>
  );
}
