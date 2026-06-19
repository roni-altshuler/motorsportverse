"use client";

import { useEffect, useRef } from "react";

/**
 * CheckeredFlagWave — site-wide animated background.
 *
 * A grid of dots painted as a black/white checkered weave (the finish-line
 * flag motif) that ripples like cloth pinned at the left "hoist": the flutter
 * grows toward the free edge on the right. Adapted from the personal-site
 * particle wave, retuned for a motorsport flag.
 *
 * Lightweight + a11y by design: a single 2D canvas (no WebGL), DPR capped at
 * 2, RAF paused when the tab is hidden, and a frozen single frame under
 * `prefers-reduced-motion`.
 */

// Grid layout
const SPACING = 32; // px between dot centers
const MOBILE_BREAKPOINT = 768;

// Wave parameters — flag flutter: a touch faster and more diagonal than an
// ocean swell, so the checker reads as cloth caught in the slipstream.
const BASE_RADIUS = 0.9; // smallest dot radius (px)
const RADIUS_RANGE = 2.0; // peak-to-peak swing on top of BASE_RADIUS (px)
const PULSE_SPEED = 0.0032; // rad/ms
const WAVE_K_X = 0.55; // wave phase per column — primary travel axis
const WAVE_K_Y = 0.25; // wave phase per row — diagonal cloth shear
const PHASE_JITTER = 0.06; // light jitter — keeps the ripple organic
const BOB_AMP = 6; // vertical bob (px) at the free edge

// Checkered-flag palette — bright (near-white) vs dim (cool grey) cells. On the
// near-black canvas this reads as a checkered weave without an opaque sheet.
const BRIGHT_RGB = "rgb(244, 247, 251)"; // ~ host --ink
const DIM_RGB = "rgb(120, 135, 160)";
const BRIGHT_ALPHA = 0.85;
const DIM_ALPHA = 0.1;

interface WaveState {
  dpr: number;
  width: number;
  height: number;
  cols: number;
  rows: number;
  offsetX: number;
  offsetY: number;
  spacing: number;
  jitter: Float32Array;
  reducedMotion: boolean;
  rafId: number;
  running: boolean;
}

export default function CheckeredFlagWave() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const state: WaveState = {
      dpr: Math.min(window.devicePixelRatio || 1, 2),
      width: 0,
      height: 0,
      cols: 0,
      rows: 0,
      offsetX: 0,
      offsetY: 0,
      spacing: SPACING,
      jitter: new Float32Array(0),
      reducedMotion: false,
      rafId: 0,
      running: false,
    };

    const layout = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      state.width = w;
      state.height = h;
      canvas.width = Math.floor(w * state.dpr);
      canvas.height = Math.floor(h * state.dpr);
      ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);

      state.spacing = window.innerWidth < MOBILE_BREAKPOINT ? 26 : SPACING;
      const s = state.spacing;
      state.cols = Math.ceil(w / s) + 1;
      state.rows = Math.ceil(h / s) + 1;
      // Center the grid so dots sit on a margin from the edges.
      state.offsetX = (w - (state.cols - 1) * s) / 2;
      state.offsetY = (h - (state.rows - 1) * s) / 2;

      const total = state.cols * state.rows;
      if (state.jitter.length !== total) {
        state.jitter = new Float32Array(total);
        for (let i = 0; i < total; i++) {
          state.jitter[i] = (Math.random() - 0.5) * 2 * PHASE_JITTER;
        }
      }
    };

    const draw = (now: number) => {
      ctx.clearRect(0, 0, state.width, state.height);

      const { cols, rows, offsetX, offsetY, spacing, jitter } = state;
      const t = state.reducedMotion ? 0 : now * PULSE_SPEED;
      const colSpan = cols > 1 ? cols - 1 : 1;

      for (let col = 0; col < cols; col++) {
        const x = offsetX + col * spacing;
        const colPhase = col * WAVE_K_X;
        // Flag is pinned at the hoist (left) and flaps most at the free edge.
        const env = col / colSpan;
        for (let row = 0; row < rows; row++) {
          const y = offsetY + row * spacing;
          const phase = colPhase + row * WAVE_K_Y + jitter[col * rows + row];
          // Two-frequency flutter so the ripple has a cloth-like snap.
          const wave =
            Math.sin(t + phase) * 0.7 + Math.sin(t * 1.7 + phase * 0.5) * 0.3;
          const breath = (wave + 1) * 0.5; // [0, 1]
          const r = BASE_RADIUS + breath * RADIUS_RANGE;
          const bob = state.reducedMotion ? 0 : wave * BOB_AMP * env;

          // 2×2 checker cells alternate bright/dim — the finish-flag weave.
          const cell = ((col >> 1) + (row >> 1)) & 1;
          if (cell === 1) {
            ctx.fillStyle = BRIGHT_RGB;
            ctx.globalAlpha = BRIGHT_ALPHA * (0.6 + 0.4 * breath);
          } else {
            ctx.fillStyle = DIM_RGB;
            ctx.globalAlpha = DIM_ALPHA * (0.6 + 0.4 * breath);
          }

          ctx.beginPath();
          ctx.arc(x, y + bob, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.globalAlpha = 1;
    };

    const loop = (now: number) => {
      draw(now);
      state.rafId = requestAnimationFrame(loop);
    };

    const start = () => {
      if (state.running) return;
      state.running = true;
      state.rafId = requestAnimationFrame(loop);
    };

    const stop = () => {
      state.running = false;
      cancelAnimationFrame(state.rafId);
    };

    const handleVisibility = () => {
      if (document.hidden) stop();
      else if (!state.reducedMotion) start();
    };

    const resizeObserver = new ResizeObserver(() => {
      layout();
      if (state.reducedMotion) draw(0);
    });

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleMotionChange = () => {
      const reduce = motionQuery.matches;
      state.reducedMotion = reduce;
      if (reduce) {
        stop();
        draw(0);
      } else {
        start();
      }
    };

    layout();

    state.reducedMotion = motionQuery.matches;
    if (state.reducedMotion) {
      draw(0);
    } else {
      start();
    }

    resizeObserver.observe(canvas);
    motionQuery.addEventListener("change", handleMotionChange);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", handleVisibility);
      motionQuery.removeEventListener("change", handleMotionChange);
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 0,
        transition: "none",
      }}
    />
  );
}
