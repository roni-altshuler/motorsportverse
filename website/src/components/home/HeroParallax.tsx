"use client";

import { useRef } from "react";
import { useGSAPScrollTrigger } from "@/lib/useGSAPScrollTrigger";

interface HeroParallaxProps {
  /** Optional ghost backdrop image.  Omit for the cinematic gradient-only look. */
  trackImage?: string | null;
  teamColor?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Three-layer parallax hero stack: ghosted track silhouette, paddock
 * gradient wash, scanline overlay.  GSAP ScrollTrigger translates
 * layers at differing speeds while the hero is in view.  Skips
 * entirely under reduced motion.
 */
export default function HeroParallax({
  trackImage = null,
  teamColor = "var(--accent-live)",
  children,
  className,
}: HeroParallaxProps) {
  const wrapRef = useRef<HTMLElement | null>(null);
  const layer1Ref = useRef<HTMLDivElement | null>(null);
  const layer2Ref = useRef<HTMLDivElement | null>(null);
  const layer3Ref = useRef<HTMLDivElement | null>(null);

  useGSAPScrollTrigger(
    wrapRef,
    (gsap, ScrollTrigger, el) => {
      const ctx = gsap.context(() => {
        if (layer1Ref.current) {
          gsap.to(layer1Ref.current, {
            yPercent: -10,
            ease: "none",
            scrollTrigger: {
              trigger: el,
              start: "top top",
              end: "bottom top",
              scrub: 0.6,
            },
          });
        }
        if (layer2Ref.current) {
          gsap.to(layer2Ref.current, {
            yPercent: -4,
            ease: "none",
            scrollTrigger: {
              trigger: el,
              start: "top top",
              end: "bottom top",
              scrub: 0.8,
            },
          });
        }
        if (layer3Ref.current) {
          gsap.to(layer3Ref.current, {
            yPercent: 3,
            ease: "none",
            scrollTrigger: {
              trigger: el,
              start: "top top",
              end: "bottom top",
              scrub: 0.4,
            },
          });
        }
      }, el);
      return () => ctx.revert();
    },
    [trackImage, teamColor],
  );

  return (
    <section
      ref={wrapRef}
      className={`relative overflow-hidden ${className ?? ""}`}
      style={{ ["--team-color" as string]: teamColor } as React.CSSProperties}
    >
      {/* Abstract gradient backdrop — no track imagery, all CSS */}
      <div
        ref={layer1Ref}
        aria-hidden
        className="absolute inset-0 -z-30 will-change-transform"
        style={{
          background: `
            radial-gradient(ellipse 80% 60% at 20% 0%, color-mix(in srgb, ${teamColor} 22%, transparent) 0%, transparent 60%),
            radial-gradient(ellipse 60% 80% at 90% 100%, color-mix(in srgb, ${teamColor} 14%, transparent) 0%, transparent 55%),
            var(--bg)
          `,
        }}
      />
      <div
        ref={layer2Ref}
        aria-hidden
        className="absolute inset-0 -z-20 will-change-transform"
        style={{
          background: "linear-gradient(180deg, transparent 0%, var(--bg) 95%)",
        }}
      />
      <div
        ref={layer3Ref}
        aria-hidden
        className="absolute inset-0 -z-10 will-change-transform pointer-events-none"
        style={{
          background: "var(--gradient-scanline)",
          mixBlendMode: "overlay",
          opacity: 0.35,
        }}
      />
      {/* Optional ghost imagery — present only if explicitly passed in.  Off by default. */}
      {trackImage && (
        <div
          aria-hidden
          className="absolute inset-0 -z-25"
          style={{
            backgroundImage: `url("${trackImage}")`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat",
            opacity: 0.12,
            filter: "grayscale(0.6) contrast(1.05)",
          }}
        />
      )}
      {children}
      <div className="telemetry-strip mt-12" aria-hidden />
    </section>
  );
}
