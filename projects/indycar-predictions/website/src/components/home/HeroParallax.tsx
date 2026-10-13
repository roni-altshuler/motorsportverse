"use client";

import { DotPattern } from "@/components/magicui/dot-pattern";
import type { CircuitGeometry } from "@/types/circuit";

interface HeroParallaxProps {
  /** Static hero surface; legacy geometry props never render a backdrop. */
  geometry?: CircuitGeometry | null;
  children: React.ReactNode;
  className?: string;
}

/** Static hero surface; legacy geometry props never render a backdrop. */
export default function HeroParallax({
  children,
  className,
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
      <div aria-hidden className="hero-photo-band__scrim" />
      <div className="hero-photo-band__content min-w-0">{children}</div>
    </section>
  );
}
