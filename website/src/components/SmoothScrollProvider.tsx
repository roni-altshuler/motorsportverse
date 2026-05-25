"use client";

import { useEffect } from "react";

/**
 * Lenis-driven smooth scroll provider. Loaded dynamically post-hydration
 * and skipped entirely when the user prefers reduced motion. Lenis
 * interferes with assistive-tech anchor jumps so consumers can opt
 * specific elements out with `data-lenis-prevent` (handled natively).
 *
 * Behaviour:
 *   • Starts/stops live in response to OS `prefers-reduced-motion` changes.
 *   • Pauses the RAF when the tab is hidden so background tabs don't
 *     burn CPU.
 */
export default function SmoothScrollProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (typeof window === "undefined") return;

    let lenis: import("lenis").default | null = null;
    let rafId = 0;
    let cancelled = false;

    const stop = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      lenis?.destroy();
      lenis = null;
    };

    const tick = (time: number) => {
      lenis?.raf(time);
      rafId = requestAnimationFrame(tick);
    };

    const start = async () => {
      if (lenis || cancelled) return;
      const { default: Lenis } = await import("lenis");
      if (cancelled) return;
      lenis = new Lenis({
        duration: 1.05,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel: true,
      });
      if (document.visibilityState === "visible") {
        rafId = requestAnimationFrame(tick);
      }
    };

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    const applyMotionPref = () => {
      if (motionQuery.matches) {
        stop();
      } else {
        void start();
      }
    };

    const handleVisibility = () => {
      if (motionQuery.matches || !lenis) return;
      if (document.visibilityState === "visible") {
        if (!rafId) rafId = requestAnimationFrame(tick);
      } else if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      }
    };

    applyMotionPref();
    motionQuery.addEventListener("change", applyMotionPref);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      cancelled = true;
      motionQuery.removeEventListener("change", applyMotionPref);
      document.removeEventListener("visibilitychange", handleVisibility);
      stop();
    };
  }, []);

  return <>{children}</>;
}
