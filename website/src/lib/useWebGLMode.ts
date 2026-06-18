"use client";

/**
 * useWebGLMode — the single source of truth for "should this client run the
 * heavy GPU/3D effects, freeze them, or skip them entirely".
 *
 * Extracted from VerseHero so the WebGL starfield (VerseCanvas), the shader
 * background, and the Spline 3D scene all share ONE capability gate and one
 * reduced-motion source of truth.
 *
 *   - "reduced" → prefers-reduced-motion: render a single static frame, no RAF.
 *   - "webgl"   → WebGL2 present, wide viewport, fine pointer, ≥4 cores: go full.
 *   - "static"  → anything else: the CSS fallback backdrop stands alone.
 *
 * Always returns "static" during SSR / first paint (so it never participates in
 * `next build` / static export and the first paint is never blank), then
 * re-evaluates on mount and on resize / reduced-motion change.
 */

import { useEffect, useState } from "react";

export type WebGLMode = "static" | "webgl" | "reduced";

export function useWebGLMode(): WebGLMode {
  const [mode, setMode] = useState<WebGLMode>("static");

  useEffect(() => {
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const evaluate = () => {
      if (mql.matches) {
        setMode("reduced");
        return;
      }
      const wideEnough = window.innerWidth >= 768;
      const finePointer = window.matchMedia("(pointer: fine)").matches;
      const cores = navigator.hardwareConcurrency ?? 4;
      let webglOk = false;
      try {
        const c = document.createElement("canvas");
        webglOk = !!c.getContext("webgl2");
      } catch {
        webglOk = false;
      }
      setMode(webglOk && wideEnough && finePointer && cores >= 4 ? "webgl" : "static");
    };
    evaluate();
    mql.addEventListener("change", evaluate);
    window.addEventListener("resize", evaluate, { passive: true });
    return () => {
      mql.removeEventListener("change", evaluate);
      window.removeEventListener("resize", evaluate);
    };
  }, []);

  return mode;
}
