"use client";

/**
 * VerseCanvas — a dependency-free WebGL "verse": a slowly-rotating 3D
 * starfield/grid of points with a few brighter "sport nodes" orbiting a
 * central core, rendered with raw WebGL2 (no three.js, zero new deps).
 *
 * Design intent: Linear/Vercel premium-dark — restrained, cinematic, the
 * crimson accent used sparingly against cool neutrals.
 *
 * Robustness contract (matches the static-export + a11y constraints):
 *   - This module is ONLY ever loaded via a dynamic import with ssr:false,
 *     so nothing here runs during `next build` / static export.
 *   - If WebGL2 is unavailable, or the context is lost, it silently renders
 *     nothing and the parent's CSS gradient remains the backdrop.
 *   - Honors prefers-reduced-motion (passed in) by freezing the animation.
 *   - Pauses when the tab is hidden or the hero scrolls out of view.
 */

import { useEffect, useRef } from "react";

interface VerseCanvasProps {
  /** Hex accents for the orbiting sport nodes, in orbit order. */
  nodeColors?: string[];
  /** Freeze animation (reduced motion). Still renders one static frame. */
  reduced?: boolean;
}

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  const v = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
  const n = parseInt(v, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

const VERT = `#version 300 es
precision highp float;
in vec3 a_pos;       // base position on/near a sphere shell
in float a_seed;     // per-point pseudo-random seed
in float a_size;     // base point size
in vec3 a_color;     // per-point color
uniform float u_time;
uniform float u_aspect;
uniform float u_dpr;
out float v_alpha;
out vec3 v_color;

void main() {
  // Slow tumble of the whole verse.
  float t = u_time * 0.06;
  float ca = cos(t), sa = sin(t);
  float cb = cos(t * 0.6), sb = sin(t * 0.6);
  vec3 p = a_pos;
  // rotate around Y
  p = vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);
  // rotate around X a touch
  p = vec3(p.x, cb * p.y - sb * p.z, sb * p.y + cb * p.z);

  // gentle breathing per-point
  float pulse = 0.85 + 0.15 * sin(u_time * 0.8 + a_seed * 6.2831);

  // simple perspective
  float depth = 2.6;
  float z = p.z + depth;
  vec2 proj = p.xy / z;
  proj.x /= u_aspect;

  gl_Position = vec4(proj, 0.0, 1.0);
  gl_PointSize = a_size * u_dpr * pulse * (1.8 / z);

  // fade points that are behind the core, keep depth cueing subtle
  v_alpha = clamp((p.z + 1.4) / 2.8, 0.08, 1.0) * pulse;
  v_color = a_color;
}`;

const FRAG = `#version 300 es
precision highp float;
in float v_alpha;
in vec3 v_color;
out vec4 outColor;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  // soft round point with a bright core
  float a = smoothstep(0.5, 0.0, d);
  a *= a;
  outColor = vec4(v_color, a * v_alpha);
}`;

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const sh = gl.createShader(type);
  if (!sh) return null;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    gl.deleteShader(sh);
    return null;
  }
  return sh;
}

export default function VerseCanvas({ nodeColors = [], reduced = false }: VerseCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let gl: WebGL2RenderingContext | null = null;
    try {
      gl = canvas.getContext("webgl2", {
        antialias: true,
        alpha: true,
        premultipliedAlpha: true,
        powerPreference: "low-power",
      });
    } catch {
      gl = null;
    }
    if (!gl) return; // parent CSS gradient stays as the backdrop

    const program = gl.createProgram();
    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!program || !vs || !fs) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    // ---- Build the point cloud: a sphere shell of cool neutral stars +
    //      a handful of brighter accent "sport nodes" on a ring. ----
    const STAR_COUNT = 1400;
    const nodes = nodeColors.length ? nodeColors.slice(0, 8) : ["#e7102f"];
    const total = STAR_COUNT + nodes.length;

    const pos = new Float32Array(total * 3);
    const seed = new Float32Array(total);
    const size = new Float32Array(total);
    const color = new Float32Array(total * 3);

    // base star color: cool silver/blue
    const starA = hexToRgb("#9fb2c9");
    const starB = hexToRgb("#3a4a63");

    for (let i = 0; i < STAR_COUNT; i++) {
      // fibonacci-ish sphere with jitter for a shell, biased toward a disc
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const r = 0.7 + Math.random() * 0.55;
      const flatten = 0.62; // squash into a disc/galaxy feel
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.cos(phi) * flatten;
      pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
      seed[i] = Math.random();
      size[i] = 1.1 + Math.random() * 2.2;
      const mix = Math.random();
      color[i * 3] = starB[0] + (starA[0] - starB[0]) * mix;
      color[i * 3 + 1] = starB[1] + (starA[1] - starB[1]) * mix;
      color[i * 3 + 2] = starB[2] + (starA[2] - starB[2]) * mix;
    }

    // sport nodes on an orbiting ring
    for (let j = 0; j < nodes.length; j++) {
      const i = STAR_COUNT + j;
      const ang = (j / nodes.length) * Math.PI * 2;
      const ringR = 1.15;
      pos[i * 3] = Math.cos(ang) * ringR;
      pos[i * 3 + 1] = Math.sin(ang * 1.3) * 0.18;
      pos[i * 3 + 2] = Math.sin(ang) * ringR;
      seed[i] = j / nodes.length;
      size[i] = 7.5;
      const c = hexToRgb(nodes[j]);
      color[i * 3] = c[0];
      color[i * 3 + 1] = c[1];
      color[i * 3 + 2] = c[2];
    }

    const mkBuf = (data: Float32Array, attr: string, n: number) => {
      const buf = gl!.createBuffer();
      gl!.bindBuffer(gl!.ARRAY_BUFFER, buf);
      gl!.bufferData(gl!.ARRAY_BUFFER, data, gl!.STATIC_DRAW);
      const loc = gl!.getAttribLocation(program, attr);
      gl!.enableVertexAttribArray(loc);
      gl!.vertexAttribPointer(loc, n, gl!.FLOAT, false, 0, 0);
      return buf;
    };
    mkBuf(pos, "a_pos", 3);
    mkBuf(seed, "a_seed", 1);
    mkBuf(size, "a_size", 1);
    mkBuf(color, "a_color", 3);

    const uTime = gl.getUniformLocation(program, "u_time");
    const uAspect = gl.getUniformLocation(program, "u_aspect");
    const uDpr = gl.getUniformLocation(program, "u_dpr");

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE); // additive — glows nicely on dark
    gl.clearColor(0, 0, 0, 0);

    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      const w = canvas.clientWidth || 1;
      const h = canvas.clientHeight || 1;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      gl!.viewport(0, 0, canvas.width, canvas.height);
      gl!.uniform1f(uAspect, w / h);
      gl!.uniform1f(uDpr, dpr);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf = 0;
    let running = true;
    const start = performance.now();

    const draw = (now: number) => {
      if (!running) return;
      const t = reduced ? 6.0 : (now - start) / 1000;
      gl!.clear(gl!.COLOR_BUFFER_BIT);
      gl!.uniform1f(uTime, t);
      gl!.drawArrays(gl!.POINTS, 0, total);
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    // pause when offscreen / hidden to save battery
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries[0]?.isIntersecting ?? true;
        if (vis && !running && !reduced) {
          running = true;
          raf = requestAnimationFrame(draw);
        } else if (!vis) {
          running = false;
          cancelAnimationFrame(raf);
        }
      },
      { threshold: 0.01 },
    );
    io.observe(canvas);

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!reduced) {
        running = true;
        raf = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const onLost = (e: Event) => {
      e.preventDefault();
      running = false;
      cancelAnimationFrame(raf);
    };
    canvas.addEventListener("webglcontextlost", onLost);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("webglcontextlost", onLost);
      const ext = gl!.getExtension("WEBGL_lose_context");
      ext?.loseContext();
    };
  }, [nodeColors, reduced]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full"
      aria-hidden
      style={{ display: "block" }}
    />
  );
}
