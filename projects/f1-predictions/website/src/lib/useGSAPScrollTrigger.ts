"use client";

import { useEffect, type RefObject } from "react";

type GSAPModule = typeof import("gsap");
type ScrollTriggerModule = typeof import("gsap/ScrollTrigger");

type Builder = (
  gsap: GSAPModule["gsap"],
  ScrollTrigger: ScrollTriggerModule["ScrollTrigger"],
  el: HTMLElement,
) => void | (() => void);

let modulePromise: Promise<{ gsap: GSAPModule["gsap"]; ScrollTrigger: ScrollTriggerModule["ScrollTrigger"] }> | null = null;

async function loadGSAP() {
  if (!modulePromise) {
    modulePromise = (async () => {
      const [gsapMod, stMod] = await Promise.all([
        import("gsap"),
        import("gsap/ScrollTrigger"),
      ]);
      gsapMod.gsap.registerPlugin(stMod.ScrollTrigger);
      return { gsap: gsapMod.gsap, ScrollTrigger: stMod.ScrollTrigger };
    })();
  }
  return modulePromise;
}

/**
 * Declarative GSAP + ScrollTrigger wrapper.  Dynamic-imports gsap on
 * first call (keeps it off the critical path) and short-circuits
 * entirely when the user prefers reduced motion.
 */
export function useGSAPScrollTrigger(
  ref: RefObject<HTMLElement | null>,
  builder: Builder,
  deps: React.DependencyList = [],
): void {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let cleanupBuilder: (() => void) | void;
    let disposed = false;
    let triggers: { kill: () => void }[] = [];

    loadGSAP().then(({ gsap, ScrollTrigger }) => {
      if (disposed) return;
      const before = ScrollTrigger.getAll();
      cleanupBuilder = builder(gsap, ScrollTrigger, el);
      triggers = ScrollTrigger.getAll().filter((t) => !before.includes(t));
    });

    return () => {
      disposed = true;
      if (typeof cleanupBuilder === "function") cleanupBuilder();
      triggers.forEach((t) => t.kill());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
