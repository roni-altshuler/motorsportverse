"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

type LenisInstance = import("lenis").default;

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
 *   • Forces scroll-to-top on every Next.js App Router navigation —
 *     Lenis maintains its own scroll counter that doesn't reset on
 *     route change, which leaves new pages stranded mid-page with the
 *     header cut off. We sync Lenis to (0, 0) on every pathname / query
 *     change, except when the URL has a hash fragment (anchor jump).
 */
export default function SmoothScrollProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const lenisRef = useRef<LenisInstance | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (typeof window === "undefined") return;

    let rafId = 0;
    let cancelled = false;

    const stop = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      lenisRef.current?.destroy();
      lenisRef.current = null;
    };

    const tick = (time: number) => {
      lenisRef.current?.raf(time);
      rafId = requestAnimationFrame(tick);
    };

    const start = async () => {
      if (lenisRef.current || cancelled) return;
      const { default: Lenis } = await import("lenis");
      if (cancelled) return;
      lenisRef.current = new Lenis({
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
      if (motionQuery.matches || !lenisRef.current) return;
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

  // On every route change, reset scroll to the top of the new page.
  // Skip when the URL has a hash fragment so #-anchor navigation still works.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.location.hash) return;
    const lenis = lenisRef.current;
    if (lenis) {
      lenis.scrollTo(0, { immediate: true, force: true });
    } else {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  }, [pathname]);

  return <>{children}</>;
}
