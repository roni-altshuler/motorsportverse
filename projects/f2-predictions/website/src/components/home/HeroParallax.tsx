"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";

interface HeroParallaxProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Hero band for RaceIQ F2. Ported from the F1 HeroParallax, but the F2 export
 * ships no circuit vector geometry, so this variant drops the animated
 * track-ribbon sweep entirely and leans on a CSS radial-gradient backdrop plus
 * the dot-pattern depth substrate. Per project convention we never ghost a
 * track map behind the hero. The dot pattern is the only motion-bearing
 * element and the global `prefers-reduced-motion` guard in globals.css
 * neutralises it.
 */
export default function HeroParallax({ children, className }: HeroParallaxProps) {
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
      <div aria-hidden className="hero-photo-band__scrim" />
      <div className="hero-photo-band__content">{children}</div>
    </section>
  );
}
