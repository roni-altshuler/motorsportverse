"use client";

/**
 * SplineShowcase — a dedicated cinematic 3D band that mounts an interactive
 * Spline scene inside a liquid-glass pane. Kept in its own section (rather than
 * stacked into the hero) so we never run three WebGL contexts in one viewport.
 *
 * Degradation: only mounts the Spline scene when the shared capability gate
 * reports "webgl"; otherwise a static gradient poster stands in. The scene
 * itself is lazy + error-boundaried (see SplineScene), so first paint is never
 * blocked and an offline/404 scene degrades to the poster.
 */

import dynamic from "next/dynamic";

import { useWebGLMode } from "@/lib/useWebGLMode";

const SplineScene = dynamic(() => import("@/components/hero/SplineScene"), { ssr: false });

export function SplineShowcase() {
  const mode = useWebGLMode();

  return (
    <section className="section pt-0">
      <div className="shell">
        <div className="liquid-glass-pane relative overflow-hidden rounded-[var(--radius-lg)]">
          <div className="grid items-center gap-8 p-8 sm:p-12 lg:grid-cols-2">
            {/* copy */}
            <div className="relative z-10">
              <p className="eyebrow eyebrow-accent eyebrow-tick">Rendered in real time</p>
              <h2 className="mt-3 text-[length:var(--text-4xl)]">
                A living model of the grid.
              </h2>
              <p className="lead mt-4 max-w-md">
                Every projection, every probability surface — spun up from one shared core and
                streamed into an interactive, GPU-rendered scene. Drag to explore.
              </p>
            </div>

            {/* 3D stage */}
            <div className="relative h-[320px] w-full sm:h-[420px]">
              {/* static poster — always painted behind, the legibility + fallback base */}
              <div
                className="pointer-events-none absolute inset-0 rounded-[var(--radius-md)]"
                style={{
                  background:
                    "radial-gradient(60% 60% at 60% 40%, var(--accent-glow-soft) 0%, transparent 70%), var(--mesh-2)",
                }}
                aria-hidden
              />
              {mode === "webgl" && (
                <div className="absolute inset-0">
                  <SplineScene className="h-full w-full" />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
