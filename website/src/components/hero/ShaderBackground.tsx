"use client";

/**
 * ShaderBackground — a dependency-free WebGL2 fragment-shader backdrop: a slow,
 * domain-warped fbm "aurora" tinted with the brand crimson over cool neutrals.
 *
 * Mirrors the VerseCanvas robustness contract (see that file):
 *   - Only ever loaded via dynamic import with ssr:false — never runs in `next build`.
 *   - Silently renders nothing if WebGL2 is unavailable or the context is lost;
 *     the parent's CSS gradient remains the backdrop.
 *   - `reduced` (prefers-reduced-motion) freezes to a single static frame.
 *   - Pauses RAF when the tab is hidden or the element scrolls offscreen.
 *
 * Purely decorative: pointer-events-none, aria-hidden, sits behind content.
 */

import { useEffect, useRef } from "react";

interface ShaderBackgroundProps {
  /** Freeze animation (reduced motion). Still renders one static frame. */
  reduced?: boolean;
  /** Primary accent (crimson by default), as 0–1 rgb is derived from this hex. */
  accent?: string;
}

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  const v = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
  const n = parseInt(v, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

const VERT = `#version 300 es
precision highp float;
// Fullscreen triangle — no attributes needed (gl_VertexID trick).
out vec2 v_uv;
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  v_uv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const FRAG = `#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 outColor;
uniform float u_time;
uniform vec2  u_res;
uniform vec3  u_accent;   // crimson
uniform vec3  u_cool;     // cool blue/teal secondary

// --- value noise + fbm ---
float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 5; i++) {
    v += amp * noise(p);
    p *= 2.02;
    amp *= 0.5;
  }
  return v;
}

void main() {
  // aspect-correct uv centered-ish
  vec2 uv = v_uv;
  vec2 p = uv;
  p.x *= u_res.x / u_res.y;

  float t = u_time * 0.04;

  // domain warp for the flowing aurora
  vec2 q = vec2(fbm(p * 1.4 + vec2(0.0, t)), fbm(p * 1.4 + vec2(5.2, -t)));
  vec2 r = vec2(fbm(p * 1.8 + 3.0 * q + vec2(1.7, 9.2) + t * 0.5),
                fbm(p * 1.8 + 3.0 * q + vec2(8.3, 2.8) - t * 0.5));
  float f = fbm(p * 1.6 + 2.5 * r);

  // shape the field into soft ridges
  float ridge = smoothstep(0.35, 0.95, f);
  float glow  = pow(ridge, 1.8);

  // vertical falloff — concentrate light toward the top, fade to nothing low
  float vfall = smoothstep(1.05, 0.15, uv.y);

  // color: cool base wash → crimson highlights on the ridges
  vec3 col = mix(u_cool * 0.5, u_accent, glow);
  float intensity = glow * vfall;

  // keep it restrained: low overall alpha so foreground copy stays legible
  float alpha = intensity * 0.55;
  outColor = vec4(col * intensity, alpha);
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

export default function ShaderBackground({
  reduced = false,
  accent = "#e7102f",
}: ShaderBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let gl: WebGL2RenderingContext | null = null;
    try {
      gl = canvas.getContext("webgl2", {
        antialias: false,
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

    const uTime = gl.getUniformLocation(program, "u_time");
    const uRes = gl.getUniformLocation(program, "u_res");
    const uAccent = gl.getUniformLocation(program, "u_accent");
    const uCool = gl.getUniformLocation(program, "u_cool");
    gl.uniform3fv(uAccent, hexToRgb(accent));
    gl.uniform3fv(uCool, hexToRgb("#6aa6ff"));

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); // premultiplied compositing
    gl.clearColor(0, 0, 0, 0);

    const resize = () => {
      const w = canvas.clientWidth || 1;
      const h = canvas.clientHeight || 1;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5); // shader is cheap-ish; cap DPR
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      gl!.viewport(0, 0, canvas.width, canvas.height);
      gl!.uniform2f(uRes, canvas.width, canvas.height);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf = 0;
    let running = true;
    const start = performance.now();

    const draw = (now: number) => {
      if (!running) return;
      const t = reduced ? 8.0 : (now - start) / 1000;
      gl!.clear(gl!.COLOR_BUFFER_BIT);
      gl!.uniform1f(uTime, t);
      gl!.drawArrays(gl!.TRIANGLES, 0, 3);
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

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
  }, [reduced, accent]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full"
      aria-hidden
      style={{ display: "block" }}
    />
  );
}
