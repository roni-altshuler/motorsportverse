"use client";

/**
 * SplineScene — a lazy, fault-tolerant wrapper around @splinetool/react-spline
 * (the 21st.dev "splite" pattern), used as an extra cinematic 3D layer in the
 * hero.
 *
 * Robustness contract (static-export + a11y + graceful degradation):
 *   - This module is only ever mounted via next/dynamic with ssr:false, AND the
 *     heavy Spline runtime is further code-split via React.lazy here — so it
 *     never participates in `next build` and never blocks first paint.
 *   - It only mounts when the shared capability gate reports "webgl" (handled by
 *     the parent), and it is wrapped in an error boundary: if the scene fails to
 *     load (offline, 404, WebGL loss), it renders nothing and the base
 *     VerseCanvas + CSS gradient remain the backdrop.
 *   - Decorative only: pointer-events-none, aria-hidden, so page copy/buttons
 *     stay interactive.
 *
 * Scene source: defaults to a public Spline scene; override per-deploy with
 * NEXT_PUBLIC_SPLINE_SCENE, or self-host a `.splinecode` under public/spline/
 * and pass `asset("/spline/<scene>.splinecode")` as the `scene` prop.
 */

import { Component, lazy, Suspense, useState, type ReactNode } from "react";

const Spline = lazy(() => import("@splinetool/react-spline"));

const DEFAULT_SCENE =
  process.env.NEXT_PUBLIC_SPLINE_SCENE ||
  "https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode";

class SilentBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    /* swallow — the CSS/WebGL fallback behind this layer stands in */
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

interface SplineSceneProps {
  scene?: string;
  className?: string;
}

export default function SplineScene({ scene = DEFAULT_SCENE, className }: SplineSceneProps) {
  const [loaded, setLoaded] = useState(false);

  return (
    <SilentBoundary>
      <Suspense fallback={null}>
        <div
          aria-hidden
          className={className}
          style={{
            height: "100%",
            width: "100%",
            opacity: loaded ? 1 : 0,
            transition: "opacity 900ms ease",
          }}
        >
          <Spline scene={scene} onLoad={() => setLoaded(true)} />
        </div>
      </Suspense>
    </SilentBoundary>
  );
}
