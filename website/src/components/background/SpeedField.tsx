"use client";

import { useEffect, useRef } from "react";

/**
 * SpeedField — site-wide cinematic motorsport background.
 *
 * Long-exposure light-trail streaks (the look of night-race photography: car
 * headlights and brake lights smeared into ribbons of light) flow across a deep
 * blue-black field, over a few slow-drifting colour glows for depth. Reads as
 * speed + motorsport without ever competing with foreground copy.
 *
 * Lightweight + a11y by design: a single 2D canvas (no WebGL), DPR capped at 2,
 * additive blending for the glow, RAF paused when the tab is hidden, and a
 * frozen single frame under `prefers-reduced-motion`.
 */

// Palette pulled from the design tokens (crimson identity + cool data hues).
const TRAIL_COLORS = [
  { rgb: "244, 247, 251", weight: 0.5 }, // silver-white (headlights) — dominant
  { rgb: "255, 45, 73", weight: 0.24 }, // crimson (brake lights / identity)
  { rgb: "56, 225, 198", weight: 0.14 }, // teal (data/AI)
  { rgb: "106, 166, 255", weight: 0.12 }, // electric blue
];

// Drifting ambient glows — give the flat field depth behind the streaks.
const GLOWS = [
  { hx: 0.5, hy: -0.05, r: 0.55, rgb: "231, 16, 47", a: 0.1, sx: 0.6, sy: 0.0, ph: 0 },
  { hx: 0.85, hy: 0.1, r: 0.4, rgb: "56, 225, 198", a: 0.06, sx: -0.4, sy: 0.3, ph: 2 },
  { hx: 0.1, hy: 0.4, r: 0.45, rgb: "106, 166, 255", a: 0.05, sx: 0.3, sy: -0.2, ph: 4 },
];

interface Trail {
  x: number;
  y: number;
  len: number; // ribbon length (px)
  thick: number; // ribbon thickness (px)
  speed: number; // px/ms
  rgb: string;
  alpha: number;
}

interface FieldState {
  dpr: number;
  width: number;
  height: number;
  trails: Trail[];
  reducedMotion: boolean;
  rafId: number;
  running: boolean;
  last: number;
}

function pickColor(): string {
  let r = Math.random();
  for (const c of TRAIL_COLORS) {
    if (r < c.weight) return c.rgb;
    r -= c.weight;
  }
  return TRAIL_COLORS[0].rgb;
}

export default function SpeedField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const state: FieldState = {
      dpr: Math.min(window.devicePixelRatio || 1, 2),
      width: 0,
      height: 0,
      trails: [],
      reducedMotion: false,
      rafId: 0,
      running: false,
      last: 0,
    };

    const spawn = (offscreen: boolean): Trail => {
      const h = state.height || 800;
      // Bands: thin/fast near the vertical centre (far lane), thick/slow toward
      // the edges (near lane) — fakes depth-of-field perspective.
      const depth = Math.random();
      const len = 120 + depth * 460;
      const thick = 0.6 + depth * 2.2;
      const speed = (0.05 + (1 - depth) * 0.16) * (state.width / 1280);
      const x = offscreen ? -len - Math.random() * state.width : Math.random() * state.width;
      return {
        x,
        y: Math.random() * h,
        len,
        thick,
        speed: Math.max(0.03, speed),
        rgb: pickColor(),
        alpha: 0.18 + depth * 0.5,
      };
    };

    const layout = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      state.width = w;
      state.height = h;
      canvas.width = Math.floor(w * state.dpr);
      canvas.height = Math.floor(h * state.dpr);
      ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);

      // Density scales with area but stays capped for perf.
      const target = Math.min(46, Math.round((w * h) / 46000));
      if (state.trails.length !== target) {
        state.trails = Array.from({ length: target }, () => spawn(false));
      }
    };

    const drawGlows = (t: number) => {
      ctx.globalCompositeOperation = "lighter";
      for (const g of GLOWS) {
        const cx = (g.hx + Math.sin(t * 0.00006 + g.ph) * 0.04 * g.sx) * state.width;
        const cy = (g.hy + Math.cos(t * 0.00006 + g.ph) * 0.06 * g.sy + g.hy * 0) * state.height;
        const rad = g.r * Math.max(state.width, state.height);
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
        grad.addColorStop(0, `rgba(${g.rgb}, ${g.a})`);
        grad.addColorStop(1, `rgba(${g.rgb}, 0)`);
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, state.width, state.height);
      }
    };

    const drawTrail = (tr: Trail) => {
      // A ribbon: faint tail → bright head, drawn as a horizontal gradient.
      const grad = ctx.createLinearGradient(tr.x, 0, tr.x + tr.len, 0);
      grad.addColorStop(0, `rgba(${tr.rgb}, 0)`);
      grad.addColorStop(0.72, `rgba(${tr.rgb}, ${tr.alpha * 0.5})`);
      grad.addColorStop(1, `rgba(${tr.rgb}, ${tr.alpha})`);
      ctx.fillStyle = grad;
      ctx.fillRect(tr.x, tr.y - tr.thick / 2, tr.len, tr.thick);
      // Bright head dot for the "light source".
      ctx.fillStyle = `rgba(${tr.rgb}, ${Math.min(1, tr.alpha + 0.15)})`;
      ctx.beginPath();
      ctx.arc(tr.x + tr.len, tr.y, tr.thick * 0.9, 0, Math.PI * 2);
      ctx.fill();
    };

    const draw = (now: number) => {
      const dt = state.last ? Math.min(64, now - state.last) : 16;
      state.last = now;

      ctx.clearRect(0, 0, state.width, state.height);
      drawGlows(state.reducedMotion ? 0 : now);

      ctx.globalCompositeOperation = "lighter";
      for (const tr of state.trails) {
        if (!state.reducedMotion) {
          tr.x += tr.speed * dt;
          if (tr.x > state.width) Object.assign(tr, spawn(true));
        }
        drawTrail(tr);
      }
      ctx.globalCompositeOperation = "source-over";
    };

    const loop = (now: number) => {
      draw(now);
      state.rafId = requestAnimationFrame(loop);
    };
    const start = () => {
      if (state.running) return;
      state.running = true;
      state.last = 0;
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
      state.reducedMotion = motionQuery.matches;
      if (state.reducedMotion) {
        stop();
        draw(0);
      } else {
        start();
      }
    };

    layout();
    state.reducedMotion = motionQuery.matches;
    if (state.reducedMotion) draw(0);
    else start();

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
