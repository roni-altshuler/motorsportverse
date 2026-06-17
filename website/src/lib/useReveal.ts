"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Failsafe scroll-reveal trigger.
 *
 * Returns a `ref` to attach to a `motion` element and a `shown` flag to drive
 * `animate={shown ? "visible" : "hidden"}`. It reveals when the element scrolls
 * into view (IntersectionObserver), but — critically — also reveals after a
 * short timeout and whenever IntersectionObserver is unavailable. That means
 * content is NEVER left permanently invisible (headless capture, reduced-motion
 * engines, prerender/no-scroll bots), while still animating in for real users.
 */
export function useReveal(rootMargin = "-60px", failsafeMs = 1400) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (shown) return;
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin },
    );
    io.observe(el);
    // Never leave content hidden if the observer never fires.
    const t = window.setTimeout(() => setShown(true), failsafeMs);
    return () => {
      io.disconnect();
      window.clearTimeout(t);
    };
  }, [shown, rootMargin, failsafeMs]);

  return { ref, shown };
}
