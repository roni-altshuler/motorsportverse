"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";
import type { CircuitGeometry } from "@/types/circuit";

interface HeroParallaxProps {
  /**
   * SVG vector geometry for the featured round's circuit. When present, an
   * animated "comet" sweep traces the track behind the hero copy (matching the
   * F1 flagship). The dash trick keeps every closed-loop path in motion
   * regardless of total length.
   */
  geometry?: CircuitGeometry | null;
  children: React.ReactNode;
  className?: string;
}

/**
 * Hero band for RaceIQ NASCAR. Ported from the F1 HeroParallax. Cup ovals
 * ship no published lap-telemetry geometry, so the
 * animated track-ribbon sweep only renders when a circuit outline exists in
 * public/data/circuits.json — otherwise the hero rests on the electric-blue
 * radial backdrop and dot-pattern substrate alone. The global
 * `prefers-reduced-motion` guard in globals.css neutralises the motion.
 */
export default function HeroParallax({
  children,
  className,
  geometry = null,
}: HeroParallaxProps) {
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
                <stop offset="0%" stopColor="var(--accent)" />
                <stop offset="50%" stopColor="#FFFFFF" />
                <stop offset="100%" stopColor="var(--accent-strong)" />
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
